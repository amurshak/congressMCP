"""In-memory segment-level FTS5 index for parsed bill text."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import AncestorNode
from .parser import ParsedBill, Unit


CONTEXT_ORDER = {"operative": 0, "quoted": 1, "header": 2}


@dataclass(frozen=True)
class RankedHit:
    unit: Unit
    score: float
    match_contexts: list[str]
    matched_queries: list[str]
    snippet: str


def sqlite_supports_fts5() -> bool:
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
              tokenize='porter unicode61 remove_diacritics 2'
            );
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

    def search(self, queries: Iterable[str], max_hits: int) -> list[RankedHit]:
        query_list = list(queries)
        limit = min(200, max(50, max_hits * 5))
        unit_rank: dict[int, dict[str, int]] = defaultdict(dict)
        unit_contexts: dict[int, set[str]] = defaultdict(set)
        unit_segments: dict[int, list[sqlite3.Row]] = defaultdict(list)

        for query in query_list:
            rows = self.conn.execute(
                """
                SELECT units.id AS unit_id, segments.id AS segment_id, segments.context, segments.text,
                       units.section_id, bm25(seg_fts) AS rank
                FROM seg_fts
                JOIN segments ON segments.id = seg_fts.rowid
                JOIN units ON units.id = segments.unit_id
                WHERE seg_fts MATCH ?
                ORDER BY bm25(seg_fts) ASC, units.section_id ASC
                LIMIT 1000
                """,
                (fts_literal(query),),
            ).fetchall()
            seen_units: set[int] = set()
            rank = 0
            for row in rows:
                unit_id = int(row["unit_id"])
                unit_contexts[unit_id].add(row["context"])
                unit_segments[unit_id].append(row)
                if unit_id in seen_units:
                    continue
                rank += 1
                if rank > limit:
                    continue
                unit_rank[unit_id][query] = rank
                seen_units.add(unit_id)

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
        return _window(prefix + chosen["text"], 320)


def _window(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def ancestor_from_json(data: str) -> list[AncestorNode]:
    return [AncestorNode(**item) for item in json.loads(data)]
