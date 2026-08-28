"""Q12 term-ladder diagnostics for search_bills (govinfo-search-spec
Addendum 4 continuation, ruled 2026-08-27).

Starved-query diagnosis by measuring ACTUAL INTERSECTIONS, never per-term
document frequency: per-term counts do not compose under AND (every term
can be individually common while the intersection is empty), so the
ladder chops text terms from the right -- one per rung -- and re-queries,
reporting the count at every rung. Rung 0 is the full query with its
count already in hand (no extra call). Each rung is a remediation the
caller can take verbatim; the chop direction operationalizes the tool
description's own remedy (re-query broader: drop words).

Two legs, both surfaced under a single ``diagnostics`` response field
that is present ONLY when something fired -- absence means "did not
fire", never "ran and found nothing":

  Text ladder (``diagnostics.term_ladder``) -- fires when the query has
  >= 2 text terms and the upstream total is < LADDER_TOTAL_THRESHOLD
  (0 included). Chop units are text terms only: a quoted phrase is one
  unit, a parenthesized boolean group without fielded operators is one
  unit, and nothing is ever split inside either. Fielded operators,
  exclusions (``NOT x`` / ``-x``), and the structured constraints are
  held fixed on every rung, and every rung sends the same sorts as the
  main query. After the single-term rung, one terminal constraints-only
  rung (``terms: []``) measures the constrained universe -- the ladder's
  true denominator -- so a dead constraint cannot misread as "your
  terms are rare". Exclusions are not constraints and are dropped from
  the terminal rung.

  Constraint leave-one-out (``diagnostics.leave_one_out``) -- fires only
  at total == 0, for any query carrying >= 1 droppable constraint,
  including pure fielded queries the text ladder never fires on (the
  nonexistent-version shape). One probe per droppable constraint, each
  omitting exactly that constraint; the omission that restores hits
  names the culprit. Droppable: caller-typed fielded operators (and
  fielded groups), the structured scope (congress, bill_type), and the
  date bounds (one unit -- they assemble to one upstream range term).
  Never droppable: the ``collection:bills`` corpus scope and the
  assembled sorts.

Every probe is labeled with exactly what it measured, and the labels
live only in the diagnostics field -- the main results never re-scope,
so the silent-re-scope failure cannot occur. A probe that errors ships
``count: null`` with ``status: "probe_failed"`` -- never ``0`` -- and
the ladder continues past it. A diagnostics failure must not alter the
main response beyond the diagnostics field: ``run_diagnostics`` returns
``None`` for "nothing fired" and swallows per-probe failures; the caller
additionally treats any exception as "no diagnostics".
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from . import govinfo_search

logger = logging.getLogger(__name__)

# Fire threshold for the text ladder: total < 10, zero included. Ruled
# 2026-08-27 (the product call the zero-only threshold was waiting on).
LADDER_TOTAL_THRESHOLD = 10

# A whole token that is a fielded operator: field:value, field:"quoted
# value", field:range(a,b). Mirrors the Q11 tokenizer's fielded shape.
_FIELDED_TOKEN_RE = re.compile(r'^[A-Za-z]+:(?:"[^"]*"|range\([^)]*\)|\S+)$')
# A fielded operator ANYWHERE inside a parenthesized group classifies the
# whole group as a constraint unit (never split; see tokenize_units).
_FIELDED_INSIDE_RE = re.compile(r"[A-Za-z]:\S")


def _scan_tokens(text: str):
    """Split a keywords string into surface tokens, keeping a quoted
    phrase, a balanced parenthesized group, and a fielded operator with a
    spaced quoted value (title:"clean energy") each as ONE token."""
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        start = i
        if text[i] == "(":
            depth = 0
            while i < n:
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
        elif text[i] == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 1
            i = min(i + 1, n)
        else:
            while i < n and not text[i].isspace():
                i += 1
            if text[start:i].count('"') == 1:
                # Mid-quote whitespace break: extend to the closing quote.
                while i < n and text[i] != '"':
                    i += 1
                i = min(i + 1, n)
        yield text[start:i]


def tokenize_units(keywords: str) -> "list[dict[str, str]]":
    """The caller's keywords as an ordered list of units, each
    ``{"kind", "text", "connector"}``.

    kinds: ``text`` (chop unit -- bare word, quoted phrase, or fielded-
    free group), ``constraint`` (fielded operator or fielded group --
    droppable in leave-one-out, held fixed in the ladder), ``fixed``
    (exclusions: ``NOT x`` / ``-x`` -- held fixed in both legs; they are
    neither text the document must contain nor a droppable constraint).
    ``connector`` is the AND/OR joiner typed before the unit; it travels
    with its unit so a chopped unit takes its joiner with it.
    """
    units: "list[dict[str, str]]" = []
    connector = ""
    negated = False
    for token in _scan_tokens(keywords):
        upper = token.upper()
        if upper in ("AND", "OR"):
            connector = token
            continue
        if upper == "NOT":
            negated = True
            continue
        if negated:
            kind, text = "fixed", f"NOT {token}"
        elif token.startswith("-") and len(token) > 1:
            kind, text = "fixed", token
        elif token.startswith("("):
            kind = ("constraint" if _FIELDED_INSIDE_RE.search(token)
                    else "text")
            text = token
        elif _FIELDED_TOKEN_RE.match(token):
            kind, text = "constraint", token
        else:
            kind, text = "text", token
        units.append({"kind": kind, "text": text, "connector": connector})
        connector = ""
        negated = False
    return units


def join_units(units: "list[dict[str, str]]") -> str:
    """Reassemble surviving units into a keywords string, dropping a
    connector whose left operand did not survive (the first emitted unit
    never carries one -- `` OR b`` is not a query)."""
    parts: "list[str]" = []
    for unit in units:
        if parts and unit["connector"]:
            parts.append(unit["connector"])
        parts.append(unit["text"])
    return " ".join(parts)


def _assemble(kw_part: str, congress: Optional[int],
              bill_type: Optional[str], from_date: Optional[str],
              to_date: Optional[str]) -> str:
    """A probe query through the SAME assembler as the main query --
    build_query appends collection:bills and the scope terms, so no probe
    can drop the corpus scope. kw_part may be empty here (the
    constraints-only rung); build_query never otherwise sees one, hence
    the strip of its leading join artifact."""
    return govinfo_search.build_query(
        kw_part, congress, bill_type,
        from_date=from_date, to_date=to_date).strip()


def probe_body(query: str) -> "dict[str, Any]":
    """Probe request body: same sorts as the main query (Q9's explicit
    relevance sort), pageSize 1 -- ``count`` is the only output a probe
    consumes and it is page-size-independent."""
    return {
        "query": query,
        "pageSize": 1,
        "offsetMark": "*",
        "sorts": [dict(sort) for sort in govinfo_search.SCORE_SORTS],
    }


async def _probe_count(post: Any, query: str) -> Optional[int]:
    """One probe: upstream count, or None on ANY failure (transport,
    non-200, unparseable body). None is the probe_failed marker -- a
    probe that errors must never look like one that counted zero."""
    try:
        response = await post(probe_body(query))
        if response.status_code != 200:
            return None
        data = response.json()
        return int(data.get("count") or 0)
    except Exception as exc:  # noqa: BLE001 -- diagnostics never raise
        logger.warning("diagnostics probe failed for %r: %s", query, exc)
        return None


def _rung(terms: "list[str]", count: Optional[int]) -> "dict[str, Any]":
    entry: "dict[str, Any]" = {"terms": terms, "count": count}
    if count is None:
        entry["status"] = "probe_failed"
    return entry


async def run_diagnostics(
    keywords: str,
    total: int,
    congress: Optional[int],
    bill_type: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    post: Any,
) -> "Optional[dict[str, Any]]":
    """Both legs, gated by their ruled fire conditions. Returns the
    ``diagnostics`` object, or None when neither leg fired -- the caller
    omits the field entirely on None (absence means "did not fire")."""
    units = tokenize_units(keywords)
    text_idx = [i for i, unit in enumerate(units) if unit["kind"] == "text"]
    diagnostics: "dict[str, Any]" = {}

    if len(text_idx) >= 2 and total < LADDER_TOTAL_THRESHOLD:
        # Rung 0: the full query, count already in hand -- no call.
        ladder = [_rung([units[i]["text"] for i in text_idx], total)]
        for keep in range(len(text_idx) - 1, 0, -1):
            kept = set(text_idx[:keep])
            surviving = [unit for i, unit in enumerate(units)
                         if unit["kind"] != "text" or i in kept]
            query = _assemble(join_units(surviving), congress, bill_type,
                              from_date, to_date)
            count = await _probe_count(post, query)
            ladder.append(
                _rung([units[i]["text"] for i in text_idx[:keep]], count))
        # Terminal rung: constraints only -- the constrained universe,
        # the ladder's denominator. Exclusions are not constraints.
        constraints = [u for u in units if u["kind"] == "constraint"]
        query = _assemble(join_units(constraints), congress, bill_type,
                          from_date, to_date)
        ladder.append(_rung([], await _probe_count(post, query)))
        diagnostics["term_ladder"] = ladder

    if total == 0:
        probes: "list[tuple[str, str]]" = []
        for index, unit in enumerate(units):
            if unit["kind"] != "constraint":
                continue
            remaining = units[:index] + units[index + 1:]
            probes.append((unit["text"],
                           _assemble(join_units(remaining), congress,
                                     bill_type, from_date, to_date)))
        full_kw = join_units(units)
        if congress is not None:
            probes.append((f"congress:{congress}",
                           _assemble(full_kw, None, bill_type,
                                     from_date, to_date)))
        if bill_type is not None:
            probes.append((f"billtype:{bill_type}",
                           _assemble(full_kw, congress, None,
                                     from_date, to_date)))
        if from_date is not None or to_date is not None:
            probes.append((
                f"publishdate:range({from_date or ''},{to_date or ''})",
                _assemble(full_kw, congress, bill_type, None, None)))
        if probes:
            results = []
            for omitted, query in probes:
                count = await _probe_count(post, query)
                entry: "dict[str, Any]" = {"omitted": omitted,
                                           "count": count}
                if count is None:
                    entry["status"] = "probe_failed"
                results.append(entry)
            diagnostics["leave_one_out"] = results

    return diagnostics or None
