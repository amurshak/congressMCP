"""Q12 term-ladder diagnostics (govinfo-search-spec Addendum 4
continuation, ruled 2026-08-27). Tests follow the ruling's own lists:

Text ladder: fires only on multi-term + total < 10; one-term and
total >= 10 -> no field; constraints and sorts preserved on every rung;
quoted phrase chops as one unit; probe failure -> null/probe_failed and
the ladder continues; rung 0 consumes no extra call.

Constraints leg: constraints-only terminal rung present whenever the
ladder fires; leave-one-out only at zero and never dropping the corpus
scope; a pure fielded zero fires leave-one-out without a text ladder;
group/phrase units never split; each probe labeled with its omission.
"""
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from congress_api.features.buckets.bills import api as mod  # noqa: E402
from congress_api.features.buckets.bills import (  # noqa: E402
    govinfo_diagnostics as gd,
)


class FakeResponse:
    def __init__(self, count=0, status_code=200):
        self.status_code = status_code
        self._count = count

    def json(self):
        return {"count": self._count, "results": [], "offsetMark": None}


def make_post(count_for=None, default=0, fail_when=None):
    """A fake govinfo_search_post recording every probe body. count_for
    maps a query substring to a count; fail_when(query) True makes that
    probe raise."""
    calls = []

    async def post(body):
        calls.append(body)
        query = body["query"]
        if fail_when is not None and fail_when(query):
            raise RuntimeError("probe transport down")
        if count_for:
            for needle, count in count_for.items():
                if needle in query:
                    return FakeResponse(count)
        return FakeResponse(default)

    return post, calls


# ---------------------------------------------------------------------------
# Fire condition (text ladder)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fires_on_multi_term_starved_and_rung0_is_free():
    post, calls = make_post(default=26)
    result = await gd.run_diagnostics(
        "radiation exposure compensation", 1, None, None, None, None, post)
    ladder = result["term_ladder"]
    # rung 0 (free) + 2 chop rungs + 1 terminal constraints-only rung
    assert len(ladder) == 4
    assert ladder[0] == {
        "terms": ["radiation", "exposure", "compensation"], "count": 1}
    assert ladder[1]["terms"] == ["radiation", "exposure"]
    assert ladder[2]["terms"] == ["radiation"]
    assert ladder[3]["terms"] == []
    # Rung 0 consumed NO call: 2 chops + 1 terminal = 3 probes exactly.
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_one_term_no_field():
    post, calls = make_post()
    assert await gd.run_diagnostics(
        "downwinders", 4, None, None, None, None, post) is None
    assert calls == []


@pytest.mark.asyncio
async def test_total_at_threshold_no_field_and_just_below_fires():
    post, calls = make_post()
    assert await gd.run_diagnostics(
        "radiation downwinders", gd.LADDER_TOTAL_THRESHOLD,
        None, None, None, None, post) is None
    assert calls == []
    fired = await gd.run_diagnostics(
        "radiation downwinders", gd.LADDER_TOTAL_THRESHOLD - 1,
        None, None, None, None, post)
    assert "term_ladder" in fired


@pytest.mark.asyncio
async def test_zero_total_multi_term_fires_ladder():
    # The threshold includes 0 (the ruled "< 10 (0 included)").
    post, _ = make_post()
    fired = await gd.run_diagnostics(
        "radiation downwinders", 0, None, None, None, None, post)
    assert "term_ladder" in fired


# ---------------------------------------------------------------------------
# Constraints and sorts preserved on every rung
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_constraints_and_sorts_on_every_rung():
    post, calls = make_post()
    await gd.run_diagnostics(
        "alpha beta docnumber:4631", 2, 119, "hr",
        "2025-01-01", "2025-06-30", post)
    assert calls, "ladder issued no probes"
    for body in calls:
        query = body["query"]
        assert "collection:bills" in query
        assert "congress:119" in query
        assert "billtype:hr" in query
        assert "publishdate:range(2025-01-01,2025-06-30)" in query
        # The caller-typed fielded operator is a constraint: held fixed
        # on every chop rung AND present in the terminal rung.
        assert "docnumber:4631" in query
        assert body["sorts"] == [{"field": "score", "sortOrder": "DESC"}]


@pytest.mark.asyncio
async def test_exclusions_held_fixed_in_ladder_dropped_from_terminal():
    post, calls = make_post()
    result = await gd.run_diagnostics(
        "alpha beta NOT gamma", 2, None, None, None, None, post)
    ladder = result["term_ladder"]
    # NOT gamma is neither a chop unit nor a droppable constraint.
    assert ladder[0]["terms"] == ["alpha", "beta"]
    assert "NOT gamma" in calls[0]["query"]
    # Exclusions are not constraints: absent from the terminal rung.
    assert "gamma" not in calls[-1]["query"]


# ---------------------------------------------------------------------------
# Unit integrity: quoted phrases and groups are never split
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quoted_phrase_chops_as_one_unit():
    post, calls = make_post()
    result = await gd.run_diagnostics(
        '"clean energy" grid', 3, None, None, None, None, post)
    ladder = result["term_ladder"]
    assert ladder[0]["terms"] == ['"clean energy"', "grid"]
    assert ladder[1]["terms"] == ['"clean energy"']
    # The phrase survives intact in the probe query -- never split.
    assert '"clean energy"' in calls[0]["query"]


@pytest.mark.asyncio
async def test_text_group_chops_as_one_unit():
    post, calls = make_post()
    result = await gd.run_diagnostics(
        "compensation (downwinders OR uranium)", 1,
        None, None, None, None, post)
    ladder = result["term_ladder"]
    assert ladder[0]["terms"] == [
        "compensation", "(downwinders OR uranium)"]
    # Chopping removes the WHOLE group; the single-term rung is the
    # first text unit alone.
    assert ladder[1]["terms"] == ["compensation"]
    assert "(downwinders OR uranium)" not in calls[0]["query"]


@pytest.mark.asyncio
async def test_fielded_group_is_a_constraint_never_split():
    post, calls = make_post()
    result = await gd.run_diagnostics(
        "judiciary (docnumber:4631 OR docnumber:5721)", 0,
        119, "hr", None, None, post)
    # One text term -> no ladder; zero total + droppable constraints
    # -> leave-one-out fires.
    assert "term_ladder" not in result
    omitted = [entry["omitted"] for entry in result["leave_one_out"]]
    assert "(docnumber:4631 OR docnumber:5721)" in omitted
    # The group's probe removed it WHOLE and kept everything else.
    group_probe = calls[omitted.index(
        "(docnumber:4631 OR docnumber:5721)")]["query"]
    assert "docnumber" not in group_probe
    assert "judiciary" in group_probe
    assert "collection:bills" in group_probe


# ---------------------------------------------------------------------------
# Probe failure: null + probe_failed, ladder continues
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_probe_failure_ships_null_and_ladder_continues():
    post, _ = make_post(
        default=7, fail_when=lambda q: q.startswith("alpha beta "))
    result = await gd.run_diagnostics(
        "alpha beta gamma", 2, None, None, None, None, post)
    ladder = result["term_ladder"]
    failed = ladder[1]  # the 2-term rung ("alpha beta") failed
    assert failed["count"] is None
    assert failed["status"] == "probe_failed"
    # The ladder continued past the failure: later rungs are real
    # counts without the failure marker.
    assert ladder[2]["count"] == 7
    assert "status" not in ladder[2]
    assert ladder[3]["count"] == 7  # terminal rung also ran


# ---------------------------------------------------------------------------
# Terminal constraints-only rung
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_terminal_rung_whenever_ladder_fires_even_nonzero():
    post, calls = make_post(default=2000)
    result = await gd.run_diagnostics(
        "alpha beta", 3, 119, "hr", None, None, post)
    terminal = result["term_ladder"][-1]
    assert terminal["terms"] == []
    assert terminal["count"] == 2000
    # Its probe is constraints-only: scope terms yes, text terms no.
    terminal_query = calls[-1]["query"]
    assert "alpha" not in terminal_query and "beta" not in terminal_query
    assert "collection:bills" in terminal_query
    assert "congress:119" in terminal_query
    assert "billtype:hr" in terminal_query


# ---------------------------------------------------------------------------
# Leave-one-out (constraints leg)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leave_one_out_only_at_zero():
    post, _ = make_post()
    nonzero = await gd.run_diagnostics(
        "alpha beta docnumber:4631", 3, 119, None, None, None, post)
    assert "leave_one_out" not in nonzero
    zero = await gd.run_diagnostics(
        "alpha beta docnumber:4631", 0, 119, None, None, None, post)
    assert "leave_one_out" in zero


@pytest.mark.asyncio
async def test_leave_one_out_never_drops_corpus_scope_and_labels_each():
    post, calls = make_post()
    result = await gd.run_diagnostics(
        "alpha docnumber:4631 billversion:enr", 0, 119, "s",
        "2025-01-01", None, post)
    entries = result["leave_one_out"]
    omitted = [entry["omitted"] for entry in entries]
    assert omitted == ["docnumber:4631", "billversion:enr",
                       "congress:119", "billtype:s",
                       "publishdate:range(2025-01-01,)"]
    # Every probe keeps the corpus scope and omits EXACTLY its label.
    loo_calls = calls[-len(entries):]
    for entry, body in zip(entries, loo_calls):
        query = body["query"]
        assert "collection:bills" in query
        assert entry["omitted"] not in query
        for other in omitted:
            if other != entry["omitted"]:
                assert other in query


@pytest.mark.asyncio
async def test_pure_fielded_zero_fires_loo_without_ladder():
    # The nonexistent-version shape: 0-1 text terms, so the text ladder
    # never fires -- leave-one-out must fire anyway on a zero.
    post, _ = make_post()
    result = await gd.run_diagnostics(
        "docnumber:99999 billversion:enr", 0, 119, "hr",
        None, None, post)
    assert "term_ladder" not in result
    omitted = [e["omitted"] for e in result["leave_one_out"]]
    assert omitted == ["docnumber:99999", "billversion:enr",
                       "congress:119", "billtype:hr"]


@pytest.mark.asyncio
async def test_zero_with_no_droppable_constraints_multi_term():
    # total 0, plain words, no scope: the ladder fires, leave-one-out
    # has nothing to drop and stays absent.
    post, _ = make_post()
    result = await gd.run_diagnostics(
        "alpha beta", 0, None, None, None, None, post)
    assert "term_ladder" in result
    assert "leave_one_out" not in result


@pytest.mark.asyncio
async def test_loo_probe_failure_labeled_not_zero():
    post, _ = make_post(fail_when=lambda q: "billversion:enr" in q)
    result = await gd.run_diagnostics(
        "docnumber:99999 billversion:enr", 0, None, None,
        None, None, post)
    entries = {e["omitted"]: e for e in result["leave_one_out"]}
    # Dropping docnumber leaves billversion:enr in the probe -> fails.
    failed = entries["docnumber:99999"]
    assert failed["count"] is None
    assert failed["status"] == "probe_failed"
    ok = entries["billversion:enr"]
    assert ok["count"] == 0 and "status" not in ok


# ---------------------------------------------------------------------------
# Wiring: search_bills carries diagnostics only when fired, and a
# diagnostics failure never alters the main response.
# ---------------------------------------------------------------------------

class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


@pytest.fixture(autouse=True)
def _keyed(monkeypatch):
    from congress_api.features.bill_text import client as _client_mod
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    monkeypatch.setattr(_client_mod, "API_KEY", "test-key-govinfo-search")


@pytest.mark.asyncio
async def test_search_bills_attaches_diagnostics_on_starved_query():
    async def post(body):
        # Main call and every probe answer count 2 with no records.
        return FakeResponse(2)

    with patch.object(mod, "govinfo_search_post", post):
        out = await mod.search_bills(
            FakeContext(), keywords="alpha beta", congress=119)
    payload = json.loads(out)
    ladder = payload["diagnostics"]["term_ladder"]
    assert ladder[0] == {"terms": ["alpha", "beta"], "count": 2}
    assert ladder[-1]["terms"] == []


@pytest.mark.asyncio
async def test_search_bills_no_diagnostics_when_not_fired():
    async def post(body):
        return FakeResponse(500)

    with patch.object(mod, "govinfo_search_post", post):
        out = await mod.search_bills(FakeContext(), keywords="alpha beta")
    assert "diagnostics" not in json.loads(out)


@pytest.mark.asyncio
async def test_search_bills_diagnostics_failure_leaves_main_response():
    # The main call succeeds; every probe raises. The response is the
    # normal corpus response with probe_failed rungs -- and even a
    # crashing run_diagnostics must not fail the search.
    state = {"calls": 0}

    async def post(body):
        state["calls"] += 1
        if state["calls"] == 1:
            return FakeResponse(0)
        raise RuntimeError("probes down")

    with patch.object(mod, "govinfo_search_post", post):
        out = await mod.search_bills(FakeContext(), keywords="alpha beta")
    payload = json.loads(out)
    assert payload["search_source"] == "govinfo_fulltext"
    assert payload["total_version_matches"] == 0
    for rung in payload["diagnostics"]["term_ladder"][1:]:
        assert rung["count"] is None
        assert rung["status"] == "probe_failed"

    async def broken(*args, **kwargs):
        raise RuntimeError("diagnostics exploded")

    state["calls"] = 0
    with patch.object(mod, "govinfo_search_post", post), \
            patch.object(mod.govinfo_diagnostics, "run_diagnostics",
                         broken):
        out = await mod.search_bills(FakeContext(), keywords="alpha beta")
    payload = json.loads(out)
    assert payload["search_source"] == "govinfo_fulltext"
    assert "diagnostics" not in payload
