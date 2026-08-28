#!/usr/bin/env python3
"""Live A1-A8 acceptance run for the GovInfo-backed search_bills
(govinfo-search-spec section 3 / section 6.6).

Runs the preregistered probes against the LIVE GovInfo endpoint through
the real tool function, archiving one JSON artifact per probe plus a
summary under runs/govinfo-search/<UTC-timestamp>/ (gitignored; cite
paths in the report). Requires a real api.data.gov key:

    CONGRESS_API_KEY=... python scripts/govinfo_search_acceptance.py

A7 (the fallback cell) poisons only the GovInfo leg with a
HOST-SELECTIVE stdlib CONNECT proxy: api.govinfo.gov is refused at
CONNECT time (502, logged), every other host tunnels for real. A blanket
dead proxy cannot prove the discrimination A7 claims -- it kills BOTH
legs whenever either builds a fresh trust_env client, so a "fallback"
outcome would be unattributable. The probe also asserts its instrument
premises before trusting the reading (a finding is only as valid as the
instrument): under the poison, a fresh client must fail against
api.govinfo.gov and succeed against api.congress.gov, and the proxy's
own deny/tunnel logs attribute the GovInfo failure to the poison rather
than a real outage.

Probes (expected outcomes preregistered in spec section 3):
  A1  exact-title reachability     -> HR 4631 in results
  A2  'Radiation Exposure Compensation' -> non-empty, relevant
  A3  differential dead            -> A2/A2+Act not byte-identical noise
  A4  zzzqqx                       -> honest zero with diagnostics
  A5  monotonicity                 -> limit=10 results prefix of limit=50
  A6  pagination                   -> pages enumerable, dup only same-id
  A7  fallback cell (poisoned proxy) -> labeled recency_window_fallback
  A8  119hr10115ih reachable by 'RECA'
  A9  time-bounding (Q10): 2025-bounded RECA -> the 2025 set (5 version
      packages / 4 bills; HR 1 matched twice) without hr10115ih;
      2026-bounded -> exactly hr10115ih; single-day 2025-07-23 ->
      exactly hr4631ih (inclusive); one-sided bounds behave; a bounded
      fallback names the updateDate semantics
  A10 Q11 snippet tri-state (Addendum 4 item 1), live, in a TEMPORARY
      snippet cache: absent when cache-empty; snippet_fetch warms and
      enrolls; cache-only re-serve; one response exhibiting all three
      states. Run standalone with:  --only A10
  A11 Q12 diagnostics (Addendum 4 continuation, redefined against the
      ladder): a starved worked-example-family query whose term_ladder
      shows the collapse rung; a one-term small-count query showing NO
      diagnostics field; a constraint-starved query (billversion:enr on
      a bill with no enrolled version) whose leave_one_out names the
      dead constraint. Run standalone with:  --only A11
"""
import asyncio
import json
import os
import socket
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402


class Ctx:
    """Minimal duck-typed context: the fallback path reaches congress.gov
    through the lifespan client."""

    class _Req:
        def __init__(self, lifespan_context):
            self.lifespan_context = lifespan_context

    def __init__(self, app_context):
        self.request_context = Ctx._Req(app_context)

    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


class HostSelectiveProxy:
    """Minimal stdlib HTTP CONNECT proxy: named hosts are refused (502 on
    CONNECT, before any egress), every other host is tunneled for real.

    Serves as A7's poison. Keeps deny/tunnel logs so the artifact can
    attribute a GovInfo transport failure to THIS instrument rather than
    to a coincidental real outage."""

    def __init__(self, deny_hosts):
        self.deny = {h.lower() for h in deny_hosts}
        self.denied = []
        self.tunneled = []
        self._srv = socket.create_server(("127.0.0.1", 0))
        self.port = self._srv.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> "HostSelectiveProxy":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        try:
            self._srv.close()
        except OSError:
            pass

    def _serve(self) -> None:
        self._srv.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,),
                             daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(15)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(65536)
                if not chunk:
                    conn.close()
                    return
                data += chunk
            request_line = data.split(b"\r\n", 1)[0].decode("latin-1")
            parts = request_line.split(" ")
            if len(parts) < 2 or parts[0].upper() != "CONNECT":
                conn.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                conn.close()
                return
            host, _, port = parts[1].partition(":")
            host = host.lower()
            if host in self.deny:
                self.denied.append(host)
                conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                conn.close()
                return
            upstream = socket.create_connection((host, int(port or 443)),
                                                timeout=15)
            self.tunneled.append(host)
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            a = threading.Thread(target=self._pipe, args=(conn, upstream),
                                 daemon=True)
            b = threading.Thread(target=self._pipe, args=(upstream, conn),
                                 daemon=True)
            a.start()
            b.start()
            a.join()
            b.join()
        except OSError:
            pass
        finally:
            for sock in (conn,):
                try:
                    sock.close()
                except OSError:
                    pass

    @staticmethod
    def _pipe(src_sock: socket.socket, dst_sock: socket.socket) -> None:
        try:
            while True:
                chunk = src_sock.recv(65536)
                if not chunk:
                    break
                dst_sock.sendall(chunk)
        except OSError:
            pass
        finally:
            for sock in (src_sock, dst_sock):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass



async def run_a10(ctx, directory, results, probe):
    """A10 (govinfo-search-spec Addendum 4 item 1): the Q11 snippet
    tri-state, LIVE. Uses a TEMPORARY snippet cache so the probe starts
    provably cache-empty and never pollutes the operator's real cache.

    Cells (each recorded either way -- a cell that cannot be exhibited is a
    FAIL to investigate, never silently skipped):
      A10_absent      cache-empty: every hit carries NEITHER snippet field
      A10_fetch       snippet_fetch=2: top-2 hits attempted (localized or
                      not_localized) and their packages land ENROLLED
      A10_cache_only  snippet_fetch=0 re-run: the warmed hits still carry
                      snippets -- only the cache could have supplied them
      A10_tristate    one response exhibiting ALL THREE states (localized +
                      not_localized + absent); candidates tried in order,
                      the exhibiting query recorded
    """
    import tempfile

    from congress_api.features.bill_text import cache as bt_cache
    from congress_api.features.bill_text import service as bt_service

    tmp_cache = tempfile.mkdtemp(prefix="a10-snippet-cache-")
    saved = os.environ.get(bt_cache.ENV_CACHE_DIR)
    os.environ[bt_cache.ENV_CACHE_DIR] = tmp_cache
    bt_service.reset_store()
    try:
        def states(payload):
            """Per-hit tri-state census. A shape violation (a fourth state:
            hollow localized, non-null not_localized snippet, or a dangling
            single field) is counted so the cell FAILS with a note instead
            of crashing the run -- the tri-state is the make-or-break."""
            out = {"localized": 0, "not_localized": 0, "absent": 0,
                   "VIOLATIONS": 0}
            for hit in payload.get("results", []):
                status = hit.get("snippet_status")
                if status == "localized":
                    out["localized"] += 1
                    if not hit.get("snippet"):
                        out["VIOLATIONS"] += 1
                elif status == "not_localized":
                    out["not_localized"] += 1
                    if hit.get("snippet") is not None:
                        out["VIOLATIONS"] += 1
                elif status is None and "snippet" not in hit \
                        and "snippet_status" not in hit:
                    out["absent"] += 1
                else:
                    out["VIOLATIONS"] += 1
            return out

        base = {"keywords": "RECA", "congress": 119}

        a = await probe(
            "A10_absent", "cache-empty: every hit in the absent state",
            dict(base),
            lambda p: (p.get("results_count", 0) >= 3
                       and states(p)["absent"] == p["results_count"]
                       and states(p)["VIOLATIONS"] == 0,
                       f"states={states(p)}"))

        b = await probe(
            "A10_fetch", "snippet_fetch=2: top-2 attempted and enrolled",
            dict(base, snippet_fetch=2),
            lambda p: (
                all((h.get("snippet_status") in ("localized", "not_localized"))
                    for h in p.get("results", [])[:2])
                and all(
                    bt_service.get_store().open(h["package_id"], None)
                    is not None
                    for h in p.get("results", [])[:2]),
                f"states={states(p)} "
                f"top2={[h.get('snippet_status') for h in p.get('results', [])[:2]]}"))

        await probe(
            "A10_cache_only",
            "snippet_fetch=0 re-run: warmed hits still carry snippets "
            "(cache is the only possible source)",
            dict(base),
            lambda p: (
                sum(1 for h in p.get("results", [])
                    if h.get("snippet_status")) >= 2,
                f"states={states(p)}"))

        # The single-response tri-state. The warmed cache persists across
        # candidates; each runs with snippet_fetch=0 so no new packages
        # enroll -- any localized/not_localized state comes from the cache,
        # and un-warmed hits stay absent.
        # not_localized needs a hit whose EVERY text term misses the
        # fronted cached text -- per-term localization makes that rare by
        # design (a good property that makes this cell the hard one). The
        # reliable generator is FORM-MATTER vocabulary: hr4631's referral
        # line ("referred to the Committee on the Judiciary") is indexed
        # upstream (measured: fielded pin + "judiciary" -> count 1) while
        # "judiciary" appears nowhere in its parsed body. The exhibit is
        # CONSTRUCTED, not hoped for (ids measured live 2026-08-27):
        #   hr5721ih  top "judiciary" hit, term in body -- pre-warmed below
        #             -> localized
        #   hr4631ih  warmed by the base cells, "judiciary" form-only
        #             -> not_localized
        #   hr1220ih  never warmed -> absent
        # A parenthesized docnumber alternation pins exactly this page
        # (grouping measured supported: "judiciary (docnumber:4631 OR
        # docnumber:1220)" -> exactly those two bills).
        await probe(
            "A10_prewarm", "warm the judiciary body-match bill (hr5721ih)",
            {"keywords": "judiciary docnumber:5721", "congress": 119,
             "bill_type": "hr", "snippet_fetch": 1},
            lambda p: (p.get("results_count", 0) == 1
                       and states(p)["VIOLATIONS"] == 0,
                       f"states={states(p)} ids={[h['package_id'] for h in p.get('results', [])]}"))
        candidates = [
            {"keywords": "judiciary (docnumber:4631 OR docnumber:5721 "
                         "OR docnumber:1220)",
             "congress": 119, "bill_type": "hr"},
            {"keywords": "judiciary", "congress": 119},
            dict(base),
        ]
        exhibited = None
        attempts = []
        from congress_api.features.buckets.bills.api import search_bills as _sb
        for kwargs in candidates:
            payload = json.loads(await _sb(ctx, **kwargs))
            st = states(payload)
            attempts.append({"request": kwargs, "states": st})
            if (st["VIOLATIONS"] == 0 and st["localized"]
                    and st["not_localized"] and st["absent"]):
                exhibited = {"request": kwargs, "states": st,
                             "response": payload}
                break
        ok = exhibited is not None
        results["A10_tristate"] = {
            "ok": ok,
            "expect": "one response exhibits localized + not_localized + absent",
            "note": (f"exhibited by {exhibited['request']} "
                     f"{exhibited['states']}" if ok
                     else f"NOT exhibited; attempts={attempts}")}
        _record(directory, "A10_tristate",
                {"attempts": attempts, "exhibited": exhibited})
        print(f"A10_tristate: {'PASS' if ok else 'FAIL'} -- "
              f"{results['A10_tristate']['note']}")
    finally:
        if saved is None:
            os.environ.pop(bt_cache.ENV_CACHE_DIR, None)
        else:
            os.environ[bt_cache.ENV_CACHE_DIR] = saved
        bt_service.reset_store()
        print(f"A10 temp cache left for inspection: {tmp_cache}")


async def run_a11(ctx, directory, results, probe):
    """A11 (govinfo-search-spec Addendum 4 continuation, ruled
    2026-08-27): the Q12 diagnostics, LIVE, per the redefined acceptance
    -- it could not exist before Q12 shipped.

    Cells:
      A11_ladder           starved multi-term query of the worked-example
                           family: term_ladder present, rung 0 carries
                           the main total with no extra call, a rung
                           where the count jumps (the collapse rung) is
                           visible, the terminal terms-[] rung measures
                           the constrained universe
      A11_one_term         one-term small-count query: NO diagnostics
                           field at all (absence means "did not fire")
      A11_dead_constraint  pure fielded zero (billversion:enr on a bill
                           with no enrolled version): leave_one_out fires
                           WITHOUT a text ladder and the billversion:enr
                           omission restores hits -- naming the culprit
    """
    def ladder_check(p):
        total = p.get("total_version_matches")
        ladder = (p.get("diagnostics") or {}).get("term_ladder")
        if not ladder:
            return False, f"no term_ladder (total={total})"
        rung0 = ladder[0]
        terminal = ladder[-1]
        chops = ladder[1:-1]
        counts = [r.get("count") for r in ladder]
        shape_ok = (rung0.get("count") == total
                    and len(rung0.get("terms", [])) >= 2
                    and terminal.get("terms") == []
                    and chops and len(chops[-1].get("terms", [])) == 1)
        # The collapse rung: some broader rung measurably above rung 0
        # (the worked example's 1 -> 26). Probe failures (count null)
        # are tolerated per-rung but cannot count as the jump.
        jump = any(isinstance(r.get("count"), int)
                   and r["count"] > (total or 0)
                   for r in chops)
        # Terminal is the denominator: at least the single-term count.
        last_chop = chops[-1].get("count") if chops else None
        denom_ok = (not isinstance(terminal.get("count"), int)
                    or not isinstance(last_chop, int)
                    or terminal["count"] >= last_chop)
        return (bool(shape_ok and jump and denom_ok),
                f"total={total} counts={counts} "
                f"terms_per_rung={[len(r.get('terms', [])) for r in ladder]}")

    await probe(
        "A11_ladder",
        "worked-example starved query: ladder with visible collapse rung",
        {"keywords": "Radiation Exposure Compensation Act amendments "
                     "downwinders", "congress": 119},
        ladder_check)

    await probe(
        "A11_one_term",
        "one-term small-count query: no diagnostics field",
        {"keywords": "judiciary docnumber:5721", "congress": 119,
         "bill_type": "hr"},
        lambda p: ("diagnostics" not in p
                   and 0 < p.get("total_version_matches", 0) < 10,
                   f"total={p.get('total_version_matches')} "
                   f"has_diagnostics={'diagnostics' in p}"))

    def dead_constraint_check(p):
        total = p.get("total_version_matches")
        diagnostics = p.get("diagnostics") or {}
        loo = diagnostics.get("leave_one_out")
        if total != 0:
            return False, (f"premise gone: total={total}, expected 0 "
                           "(does hr4631 have an enr version now?)")
        if "term_ladder" in diagnostics:
            return False, "text ladder fired on a pure fielded query"
        if not loo:
            return False, "no leave_one_out on a constrained zero"
        by_omitted = {entry.get("omitted"): entry for entry in loo}
        culprit = by_omitted.get("billversion:enr")
        named = (culprit is not None
                 and isinstance(culprit.get("count"), int)
                 and culprit["count"] > 0)
        return (named,
                f"probes={[(e.get('omitted'), e.get('count')) for e in loo]}")

    await probe(
        "A11_dead_constraint",
        "billversion:enr on an unenrolled bill: leave_one_out names it",
        {"keywords": "docnumber:4631 billversion:enr", "congress": 119,
         "bill_type": "hr"},
        dead_constraint_check)


def _out_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    directory = Path(__file__).resolve().parent.parent / "runs" / \
        "govinfo-search" / stamp
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _record(directory: Path, name: str, payload):
    (directory / f"{name}.json").write_text(
        json.dumps(payload, indent=2, default=str))


async def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default=None,
                    help="run one probe group only (supported: A10, A11)")
    args = ap.parse_args()
    if not os.getenv("CONGRESS_API_KEY") and not os.getenv("GOVINFO_API_KEY"):
        print("Set CONGRESS_API_KEY (or GOVINFO_API_KEY) first.",
              file=sys.stderr)
        return 2

    from congress_api.core.api_config import BASE_URL
    from congress_api.core.client_handler import AppContext, SimpleCache
    from congress_api.features.buckets.bills.api import search_bills

    directory = _out_dir()
    # Mirror the server lifespan's client exactly (client_handler
    # app_lifespan): make_api_request issues RELATIVE paths ('/bill/119'),
    # so a bare AsyncClient without base_url fails every congress.gov
    # request with a RequestError -- which is precisely how the first A7
    # re-run's fallback leg died while both premises held.
    app_ctx = AppContext(
        api_key=os.getenv("CONGRESS_API_KEY") or "",
        client=httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=5,
                                max_connections=10),
            follow_redirects=True,
        ),
        cache=SimpleCache(60))
    ctx = Ctx(app_ctx)
    results = {}

    async def probe(name, expect, coro_kwargs, check):
        raw = await search_bills(ctx, **coro_kwargs)
        payload = json.loads(raw)
        ok, note = check(payload)
        results[name] = {"ok": ok, "expect": expect, "note": note}
        _record(directory, name, {"request": coro_kwargs,
                                  "response": payload,
                                  "ok": ok, "note": note})
        print(f"{name}: {'PASS' if ok else 'FAIL'} -- {note}")
        return payload

    def ids(payload):
        return [r.get("package_id") for r in payload.get("results", [])]

    if args.only and args.only.upper() in ("A10", "A11"):
        if args.only.upper() == "A10":
            await run_a10(ctx, directory, results, probe)
        else:
            await run_a11(ctx, directory, results, probe)
        _record(directory, "summary", results)
        await app_ctx.client.aclose()
        failed = [k for k, v in results.items() if not v["ok"]]
        print(f"\nArtifacts: {directory}")
        print("RESULT:", "ALL PASS" if not failed else f"FAILED: {failed}")
        return 0 if not failed else 1
    if args.only:
        print(f"unknown --only group: {args.only}", file=sys.stderr)
        return 2

    # A1
    a1 = await probe(
        "A1", "HR 4631 reachable by exact title",
        {"keywords": "St. Louis RECA Readjustment Act", "congress": 119},
        lambda p: ("BILLS-119hr4631ih" in ids(p),
                   f"ids={ids(p)[:5]}"))

    # A2
    a2 = await probe(
        "A2", "no-'Act' query non-empty",
        {"keywords": "Radiation Exposure Compensation", "congress": 119},
        lambda p: (p.get("results_count", 0) > 0,
                   f"count={p.get('total_version_matches')}"))

    # A3: differential dead -- not byte-identical to A1's list, and the
    # 'Act'-ful variant is not a newest-bills page either.
    a3b = await probe(
        "A3", "differential dead",
        {"keywords": "Radiation Exposure Compensation Act", "congress": 119},
        lambda p: (p.get("results_count", 0) > 0, "with-Act non-empty"))
    a3_ok = (json.dumps(a1.get("results")) != json.dumps(a3b.get("results"))
             or ids(a1) == ids(a3b) == [])
    diff_ok = json.dumps(a2.get("results")) != json.dumps(
        a1.get("results"))
    results["A3"] = {"ok": bool(a3_ok and diff_ok), "expect":
                     "no byte-identical cross-query lists",
                     "note": f"a1!=a3b:{a3_ok} a2!=a1:{diff_ok}"}
    _record(directory, "A3_differential", results["A3"])
    print(f"A3: {'PASS' if results['A3']['ok'] else 'FAIL'}")

    # A4
    await probe(
        "A4", "honest diagnosable zero",
        {"keywords": "zzzqqx", "congress": 119},
        lambda p: (p.get("results_count") == 0 and "error" not in p
                   and "query_diagnostics" in p,
                   "zero with diagnostics"))

    # A5 monotonicity
    p10 = await probe("A5_limit10", "prefix base",
                      {"keywords": "Radiation Exposure Compensation",
                       "congress": 119, "limit": 10},
                      lambda p: (True, f"n={p.get('results_count')}"))
    p50 = await probe("A5_limit50", "prefix superset",
                      {"keywords": "Radiation Exposure Compensation",
                       "congress": 119, "limit": 50},
                      lambda p: (True, f"n={p.get('results_count')}"))
    prefix = ids(p10) == ids(p50)[:len(ids(p10))]
    results["A5"] = {"ok": prefix, "expect": "limit=10 is a prefix of 50",
                     "note": f"prefix={prefix}"}
    _record(directory, "A5_monotonicity", {
        "limit10": ids(p10), "limit50": ids(p50), "ok": prefix})
    print(f"A5: {'PASS' if prefix else 'FAIL'}")

    # A6 pagination walk
    walked, token, pages = [], None, 0
    while pages < 10:
        kwargs = {"keywords": "Radiation Exposure Compensation",
                  "congress": 119, "limit": 10}
        if token:
            kwargs["page_token"] = token
        payload = json.loads(await search_bills(ctx, **kwargs))
        walked.extend(ids(payload))
        pages += 1
        _record(directory, f"A6_page{pages}", payload)
        token = payload.get("next_page_token")
        if not token:
            break
    dup = [i for i in set(walked) if walked.count(i) > 1]
    # tolerated class: same bill id on adjacent pages; any dup must at
    # least be same-id (which package_id dedup shows trivially).
    results["A6"] = {"ok": token is None, "expect":
                     "walk terminates; dups only same-id",
                     "note": f"pages={pages} bills={len(walked)} "
                             f"dup_ids={dup}"}
    print(f"A6: {'PASS' if results['A6']['ok'] else 'FAIL'} "
          f"({results['A6']['note']})")

    # A7 fallback cell: GovInfo unreachable while congress.gov stays
    # reachable. The poison is host-selective (see module docstring) --
    # a blanket dead proxy kills both legs and makes the outcome
    # unattributable. Premises are asserted BEFORE the probe runs; if
    # either fails, A7 is recorded VOID (instrument failure), never
    # PASS or FAIL.
    proxy = HostSelectiveProxy(deny_hosts=["api.govinfo.gov"]).start()
    saved_env = {name: os.environ.get(name)
                 for name in ("HTTPS_PROXY", "HTTP_PROXY")}
    os.environ["HTTPS_PROXY"] = proxy.url
    os.environ["HTTP_PROXY"] = proxy.url
    premise = {"govinfo_dead": False, "congress_alive": False}
    try:
        # Premise 1: under the poison, a FRESH trust_env client (the same
        # construction class govinfo_search_post uses) must fail against
        # GovInfo -- refused at CONNECT, so no quota is spent and no key
        # is needed.
        try:
            async with httpx.AsyncClient(timeout=10.0) as fresh:
                await fresh.get("https://api.govinfo.gov/search")
            premise["govinfo_unexpected"] = "request succeeded"
        except httpx.HTTPError as exc:
            premise["govinfo_dead"] = True
            premise["govinfo_error"] = type(exc).__name__
        # Premise 2: the SAME environment must let a fresh client reach
        # congress.gov (any HTTP status is reachability; auth is not the
        # premise).
        try:
            async with httpx.AsyncClient(timeout=20.0) as fresh:
                resp = await fresh.get(
                    "https://api.congress.gov/v3/bill",
                    params={"format": "json"})
            premise["congress_alive"] = True
            premise["congress_status"] = resp.status_code
        except httpx.HTTPError as exc:
            premise["congress_error"] = type(exc).__name__
        premise_ok = premise["govinfo_dead"] and premise["congress_alive"]

        if premise_ok:
            a7 = json.loads(await search_bills(
                ctx, keywords="climate", congress=119))
        else:
            a7 = {"instrument_error": "A7 premise assertions failed; "
                                      "probe not run"}
    finally:
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        proxy.stop()
    # Attribution: the GovInfo failure must be OUR refusal, on the record.
    premise["proxy_denied_hosts"] = sorted(set(proxy.denied))
    premise["proxy_tunneled_hosts"] = sorted(set(proxy.tunneled))
    attributed = "api.govinfo.gov" in premise["proxy_denied_hosts"]
    if not premise_ok or not attributed:
        results["A7"] = {"ok": False, "expect":
                         "labeled fallback, structurally distinguishable",
                         "note": "VOID: instrument premises not "
                                 f"established ({premise})",
                         "premise": premise}
    else:
        a7_ok = (a7.get("search_source") == "recency_window_fallback"
                 and a7.get("fallback_trigger") == "govinfo_unreachable"
                 and "window" in a7)
        results["A7"] = {"ok": a7_ok, "expect":
                         "labeled fallback, structurally distinguishable",
                         "note": f"source={a7.get('search_source')} "
                                 f"trigger={a7.get('fallback_trigger')}",
                         "premise": premise}
    _record(directory, "A7", {"premise": premise, "response": a7})
    print(f"A7: {'PASS' if results['A7']['ok'] else 'FAIL'} "
          f"({results['A7']['note']})")

    # A8
    await probe(
        "A8", "119hr10115ih reachable by RECA keyword",
        {"keywords": "RECA", "congress": 119},
        lambda p: (any(str(i).startswith("BILLS-119hr10115")
                       for i in ids(p)), f"ids={ids(p)}"))

    # A9 (Q10): the tool-level end-to-end of what M5 measured raw.
    def bills_of(p):
        return sorted({(r["bill_type"], r["bill_number"])
                       for r in p.get("results", [])})

    # Spec section 3 says "the five 2025-dated bills"; measured at the
    # tool level that is FIVE VERSION PACKAGES deduping to FOUR bills
    # (HR 1 matched with both enr and eas) -- the exact granularity
    # total_version_matches exists to keep honest. Asserted as the
    # tool-level truth of the raw M5 measurement; wording flagged to the
    # spec session.
    a9_expected_2025 = [("hr", 1), ("hr", 1362), ("hr", 4631), ("s", 243)]
    await probe(
        "A9_2025", "2025-bounded RECA: the 2025 bill set (5 version "
                   "packages / 4 bills), without hr10115ih",
        {"keywords": "RECA", "congress": 119,
         "fromDateTime": "2025-01-01", "toDateTime": "2025-12-31"},
        lambda p: (bills_of(p) == a9_expected_2025
                   and p.get("total_version_matches") == 5,
                   f"bills={bills_of(p)} "
                   f"packages={p.get('total_version_matches')}"))
    await probe(
        "A9_2026", "2026-bounded RECA: exactly hr10115ih",
        {"keywords": "RECA", "congress": 119,
         "fromDateTime": "2026-01-01", "toDateTime": "2026-12-31"},
        lambda p: (ids(p) == ["BILLS-119hr10115ih"], f"ids={ids(p)}"))
    await probe(
        "A9_single_day", "2025-07-23 single-day: exactly hr4631ih "
                         "(inclusivity)",
        {"keywords": "RECA", "congress": 119,
         "fromDateTime": "2025-07-23", "toDateTime": "2025-07-23"},
        lambda p: (ids(p) == ["BILLS-119hr4631ih"], f"ids={ids(p)}"))
    await probe(
        "A9_from_only", "one-sided from 2026-01-01: exactly hr10115ih",
        {"keywords": "RECA", "congress": 119,
         "fromDateTime": "2026-01-01"},
        lambda p: (ids(p) == ["BILLS-119hr10115ih"], f"ids={ids(p)}"))
    await probe(
        "A9_to_only", "one-sided to 2025-12-31: same set as the 2025 "
                      "range, without hr10115ih",
        {"keywords": "RECA", "congress": 119,
         "toDateTime": "2025-12-31"},
        lambda p: (bills_of(p) == a9_expected_2025
                   and p.get("total_version_matches") == 5,
                   f"bills={bills_of(p)} "
                   f"packages={p.get('total_version_matches')}"))

    # A9 fallback leg: a bounded fallback names the updateDate
    # semantics. Same host-selective poison as A7; attribution via the
    # proxy's own deny log (A7 established the full premises this run).
    proxy9 = HostSelectiveProxy(deny_hosts=["api.govinfo.gov"]).start()
    saved9 = {name: os.environ.get(name)
              for name in ("HTTPS_PROXY", "HTTP_PROXY")}
    os.environ["HTTPS_PROXY"] = proxy9.url
    os.environ["HTTP_PROXY"] = proxy9.url
    try:
        a9f = json.loads(await search_bills(
            ctx, keywords="climate", congress=119,
            fromDateTime="2026-01-01", toDateTime="2026-12-31"))
    finally:
        for name, value in saved9.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        proxy9.stop()
    a9f_attributed = "api.govinfo.gov" in proxy9.denied
    a9f_ok = (a9f_attributed
              and a9f.get("search_source") == "recency_window_fallback"
              and "updateDate" in a9f.get("message", "")
              and a9f.get("date_bounds", {}).get("applied_to")
              == "updateDate")
    results["A9_fallback"] = {
        "ok": a9f_ok,
        "expect": "bounded fallback names updateDate semantics",
        "note": f"attributed={a9f_attributed} "
                f"source={a9f.get('search_source')} "
                f"date_bounds={a9f.get('date_bounds')}"}
    _record(directory, "A9_fallback", {
        "proxy_denied_hosts": sorted(set(proxy9.denied)),
        "response": a9f})
    print(f"A9_fallback: {'PASS' if a9f_ok else 'FAIL'} "
          f"({results['A9_fallback']['note']})")

    # ---- A10 (Addendum 4 item 1): the Q11 snippet tri-state ----
    await run_a10(ctx, directory, results, probe)

    # ---- A11 (Addendum 4 continuation): the Q12 diagnostics ----
    await run_a11(ctx, directory, results, probe)

    _record(directory, "summary", results)
    await app_ctx.client.aclose()
    failed = [k for k, v in results.items() if not v["ok"]]
    print(f"\nArtifacts: {directory}")
    print("RESULT:", "ALL PASS" if not failed else f"FAILED: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
