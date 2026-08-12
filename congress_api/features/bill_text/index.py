"""In-memory segment-level FTS5 index for parsed bill text."""

from __future__ import annotations

import functools
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import AncestorNode
from .parser import ParsedBill, Unit


CONTEXT_ORDER = {"operative": 0, "quoted": 1, "header": 2}

# ONE definition, used to build the segment index AND to tokenize queries for the
# zero-hit diagnostic (F10). Two copies would let the diagnostic drift into reporting
# a tokenisation the search never performed -- an instrument that reproduces the
# failure class of the thing it measures.
FTS_TOKENIZER = "porter unicode61 remove_diacritics 2"


@dataclass(frozen=True)
class RankedHit:
    unit: Unit
    score: float
    match_contexts: list[str]
    matched_queries: list[str]
    snippet: str


@dataclass(frozen=True)
class QueryDiagnosis:
    """Why a query found nothing: the terms it became, and which the bill lacks."""

    terms: list[str]
    absent: list[str]

    @property
    def verdict(self) -> str:
        # The distinction F10 exists to draw. Zero hits with every term present means
        # the words are in the bill but not adjacent in this order -- a phrasing
        # problem the caller can fix by rephrasing. Zero hits with a term missing
        # means no rephrasing will help; the concept is not in this document under
        # that word.
        return "absent_term" if self.absent else "phrasing"


@functools.cache
def sqlite_supports_fts5() -> bool:
    # Cached: this probes a COMPILE-TIME property of the linked SQLite, which cannot
    # change within a process, but every one of the three tools calls it on every
    # invocation -- so an unavoidable answer was being re-derived by opening and
    # closing a database each time.
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(text)")
        conn.close()
        return True
    except sqlite3.Error:
        return False


def fts_literal(q: str) -> str:
    return '"' + q.replace('"', '""') + '"'


def normalized_query(q: str) -> str:
    return re.sub(r"\s+", " ", q).strip().casefold()


def has_token(q: str) -> bool:
    return bool(re.search(r"[A-Za-z0-9]", q))


class BillTextIndex:
    def __init__(self, parsed: ParsedBill):
        self.parsed = parsed
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._build()

    def _build(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE units (
              id INTEGER PRIMARY KEY,
              section_id TEXT NOT NULL UNIQUE,
              ancestor_path TEXT NOT NULL,
              header TEXT,
              display_text TEXT NOT NULL,
              byte_length INTEGER NOT NULL,
              is_amendatory INTEGER NOT NULL,
              amends TEXT NOT NULL
            );

            CREATE TABLE segments (
              id INTEGER PRIMARY KEY,
              unit_id INTEGER NOT NULL REFERENCES units(id),
              ordinal INTEGER NOT NULL,
              context TEXT NOT NULL CHECK (context IN ('operative','quoted','header')),
              text TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE seg_fts USING fts5(
              text,
              content='segments',
              content_rowid='id',
              tokenize='"""
            + FTS_TOKENIZER
            + """'
            );

            -- The bill's term vocabulary, post-stemming, straight off the index that
            -- answers the search. Lets the zero-hit diagnostic ask "is this term
            -- anywhere in the document" without a second scan that could disagree.
            CREATE VIRTUAL TABLE seg_vocab USING fts5vocab(seg_fts, 'row');

            -- A scratch table for tokenizing QUERIES with the identical tokenizer.
            -- Running the query through FTS5 itself is the only way to report the
            -- tokenisation the search actually used; a Python re-implementation of
            -- Porter stemming would be a different tokeniser wearing its name.
            CREATE VIRTUAL TABLE probe_fts USING fts5(
              text,
              tokenize='"""
            + FTS_TOKENIZER
            + """'
            );
            CREATE VIRTUAL TABLE probe_vocab USING fts5vocab(probe_fts, 'row');
            """
        )
        segment_id = 1
        for unit_id, unit in enumerate(self.parsed.units, start=1):
            self.conn.execute(
                """
                INSERT INTO units(id, section_id, ancestor_path, header, display_text,
                                  byte_length, is_amendatory, amends)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    unit.section_id,
                    json.dumps([node.model_dump() for node in unit.ancestor_path]),
                    unit.header,
                    unit.display_text,
                    unit.byte_length,
                    1 if unit.is_amendatory else 0,
                    json.dumps(unit.amends),
                ),
            )
            for ordinal, segment in enumerate(unit.segments):
                self.conn.execute(
                    "INSERT INTO segments(id, unit_id, ordinal, context, text) VALUES (?, ?, ?, ?, ?)",
                    (segment_id, unit_id, ordinal, segment.context, segment.text),
                )
                segment_id += 1
        self.conn.execute("INSERT INTO seg_fts(seg_fts) VALUES('rebuild')")
        self.conn.execute("INSERT INTO seg_fts(seg_fts) VALUES('optimize')")
        self.conn.commit()

    def diagnose(self, query: str) -> QueryDiagnosis:
        """Tokenize `query` exactly as the index does, and say which terms the bill lacks.

        A zero-hit response is otherwise unreadable: "absent from the bill" and "present
        but not phrased this way" look identical, and the caller has no way to tell
        whether to rephrase or to give up on the word (F10). Reporting the terms also
        surfaces the stemming, which is where a phrase silently stops meaning what the
        caller typed.
        """
        self.conn.execute("DELETE FROM probe_fts")
        self.conn.execute("INSERT INTO probe_fts(text) VALUES (?)", (query,))
        terms = [row[0] for row in self.conn.execute("SELECT term FROM probe_vocab")]
        # fts5vocab yields terms in index (sorted) order, not query order. Sort by where
        # each stem first prefixes the query so the list reads left-to-right as typed;
        # this is display order only and never affects the absence test below.
        lowered = query.casefold()
        terms.sort(key=lambda term: (lowered.find(term[:4]), term))
        absent = [
            term
            for term in terms
            if self.conn.execute(
                "SELECT 1 FROM seg_vocab WHERE term = ? LIMIT 1", (term,)
            ).fetchone()
            is None
        ]
        return QueryDiagnosis(terms=terms, absent=absent)

    def query_matches(self, query: str) -> bool:
        """Whether `query` matches any segment at all, independent of ranking or the
        max_hits cap. The zero-hit diagnostic (F10) must key off THIS, not off the
        truncated result list: a query whose only matches were outranked out of the
        top max_hits is not a zero-hit query, and diagnosing it would assert the
        caller-facing falsehood 'every term is present but not phrased this way'
        (verdict `phrasing`) about a query that in fact matched a section. Uses the
        same phrase-literal MATCH the ranked search runs, so 'matched' means here what
        it means there."""
        if not has_token(query):
            return False
        row = self.conn.execute(
            "SELECT 1 FROM seg_fts WHERE seg_fts MATCH ? LIMIT 1", (fts_literal(query),)
        ).fetchone()
        return row is not None

    def search(self, queries: Iterable[str], max_hits: int) -> list[RankedHit]:
        query_list = list(queries)
        limit = min(200, max(50, max_hits * 5))
        unit_rank: dict[int, dict[str, int]] = defaultdict(dict)
        unit_contexts: dict[int, set[str]] = defaultdict(set)
        unit_segments: dict[int, list[sqlite3.Row]] = defaultdict(list)

        for query in query_list:
            # bm25() is an FTS5 auxiliary function usable only in the flat query
            # that owns the MATCH (in SELECT / ORDER BY -- never inside an
            # aggregate or a non-flattened subquery), so aggregate to units in
            # Python instead. Deliberately NO row LIMIT: a flat LIMIT on segment
            # rows truncated the candidate set before the per-query *unit* limit
            # could apply -- a common term yields many matching segments inside few
            # units (spec §7, defect 5e). The row set is one bill's segments.
            rows = self.conn.execute(
                """
                SELECT units.id AS unit_id, units.section_id AS section_id,
                       segments.id AS segment_id, segments.context, segments.text,
                       segments.ordinal, bm25(seg_fts) AS rank
                FROM seg_fts
                JOIN segments ON segments.id = seg_fts.rowid
                JOIN units ON units.id = segments.unit_id
                WHERE seg_fts MATCH ?
                ORDER BY bm25(seg_fts) ASC, units.section_id ASC
                """,
                (fts_literal(query),),
            ).fetchall()
            # Rows are bm25-ordered, so a unit's first appearance is its best rank.
            # Admit the first `limit` distinct units for THIS query as candidates
            # (1-based ranks); keep collecting segments for units already candidate
            # for any query, but never admit a brand-new unit past the cap.
            ranked_this_query = 0
            for row in rows:
                unit_id = int(row["unit_id"])
                existing = unit_rank.get(unit_id)
                if existing is None or query not in existing:
                    if ranked_this_query < limit:
                        ranked_this_query += 1
                        # Keyed by query string so a duplicate query collapses in
                        # the RRF sum rather than double-counting.
                        unit_rank[unit_id][query] = ranked_this_query
                    elif existing is None:
                        # New unit beyond the candidate cap and not a candidate for
                        # any other query -> drop it entirely.
                        continue
                unit_contexts[unit_id].add(row["context"])
                unit_segments[unit_id].append(row)

        hits: list[RankedHit] = []
        by_id = {idx: unit for idx, unit in enumerate(self.parsed.units, start=1)}
        for unit_id, ranks in unit_rank.items():
            score = sum(1 / (60 + rank) for rank in ranks.values())
            unit = by_id[unit_id]
            contexts = sorted(unit_contexts[unit_id], key=lambda item: CONTEXT_ORDER[item])
            snippet = self._snippet_for_unit(unit_id, unit_segments[unit_id])
            hits.append(
                RankedHit(
                    unit=unit,
                    score=score,
                    match_contexts=contexts,
                    matched_queries=sorted(ranks.keys()),
                    snippet=snippet,
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.unit.section_id))
        return hits[:max_hits]

    def _snippet_for_unit(self, unit_id: int, rows: list[sqlite3.Row]) -> str:
        preferred = [row for row in rows if row["context"] == "quoted"] or rows
        chosen = preferred[0]
        prefix = ""
        if chosen["context"] == "quoted":
            prev = self.conn.execute(
                """
                SELECT text FROM segments
                WHERE unit_id = ? AND context = 'operative'
                  AND ordinal < (SELECT ordinal FROM segments WHERE id = ?)
                ORDER BY ordinal DESC
                LIMIT 1
                """,
                (unit_id, chosen["segment_id"]),
            ).fetchone()
            if prev:
                prefix = _window(prev["text"], 90) + " "
        # Wrap a quoted snippet in delimiters (spec §6) so the caution is visible in
        # the snippet text itself, not only in match_contexts.
        chosen_text = f'"{chosen["text"]}"' if chosen["context"] == "quoted" else chosen["text"]
        return _window(prefix + chosen_text, 320)


def _window(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def ancestor_from_json(data: str) -> list[AncestorNode]:
    return [AncestorNode(**item) for item in json.loads(data)]
