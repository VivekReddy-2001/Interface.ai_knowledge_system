"""Snapshot-scoped lexical retrieval using SQLite FTS5's built-in BM25 ranking."""

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict
from threading import Lock

from knowledge_now.ingestion import SnapshotStore
from knowledge_now.models import EvidenceUnit, SearchHit
from knowledge_now.parsing import build_evidence_units

# Remove conversational filler, while retaining product names, metrics and numbers.
STOP_WORDS = frozenset(
    "a an and are as at be can could do does for from give how i in is it me my of on "
    "or our please tell than that the their them these this to us was we were what "
    "when where which who with would you your".split()
)


def query_terms(question: str) -> list[str]:
    """Split words/numbers, remove filler, and keep each term once in input order."""
    words = re.findall(r"[^\W_]+", question.casefold())
    return list(dict.fromkeys(word for word in words if word not in STOP_WORDS))


class EvidenceRetriever:
    def __init__(self, store: SnapshotStore) -> None:
        self._store = store
        self._lock = Lock()
        self._connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._tables: dict[str, str] = {}

    def prepare(self, snapshot_id: str) -> None:
        """Build once during ingestion; keep separate BM25 corpus statistics per capture."""
        with self._lock:
            if snapshot_id in self._tables:
                return
            if snapshot_id not in {info.snapshot_id for info in self._store.list_snapshots()}:
                raise ValueError(f"Unknown snapshot ID: {snapshot_id!r}")
            # Only generated hex enters the SQL identifier; never interpolate the supplied ID.
            table = "evidence_" + hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest()
            try:
                with self._connection:
                    self._connection.execute("BEGIN")
                    self._connection.execute(
                        f"CREATE VIRTUAL TABLE {table} USING fts5("
                        "body, metadata, context, unit_id UNINDEXED, url UNINDEXED, "
                        "start_line UNINDEXED, payload UNINDEXED, tokenize='porter unicode61')"
                    )
                    for page in self._store.pages(snapshot_id):
                        units = build_evidence_units(page)
                        self._connection.executemany(
                            f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                (
                                    unit.text,
                                    "\n".join([unit.title, *unit.headings, unit.url]),
                                    "\n".join([unit.context_before, unit.context_after]),
                                    unit.unit_id,
                                    unit.url,
                                    unit.start_line,
                                    json.dumps(asdict(unit), ensure_ascii=False),
                                )
                                for unit in units
                            ),
                        )
            except sqlite3.OperationalError as exc:
                if "no such module: fts5" in str(exc).lower():
                    raise RuntimeError(
                        "This Python installation needs SQLite with FTS5 enabled."
                    ) from exc
                raise
            # Mark ready only after every unit has committed successfully.
            self._tables[snapshot_id] = table

    def search(self, question: str, as_of: str | None = None, top_k: int = 5) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive.")
        selected = self._store.select(as_of)
        terms = query_terms(question)
        if selected is None or not terms:
            return []
        self.prepare(selected.snapshot_id)
        # Quote sanitized tokens so user input is never executed as FTS query syntax.
        expression = " OR ".join(f'"{term}"' for term in terms)
        with self._lock:
            table = self._tables[selected.snapshot_id]
            rows = self._connection.execute(
                f"SELECT payload, bm25({table}, 4.0, 2.0, 0.5) AS distance "
                f"FROM {table} WHERE {table} MATCH ? "
                "ORDER BY distance, url, start_line, unit_id LIMIT ?",
                (expression, top_k),
            ).fetchall()
        hits = []
        for row in rows:
            data = json.loads(row["payload"])
            data["headings"] = tuple(data["headings"])
            unit = EvidenceUnit(**data)
            # SQLite returns negative BM25 values (smaller is better); expose positive scores.
            hits.append(SearchHit(unit=unit, score=-row["distance"]))
        return hits

    def close(self) -> None:
        with self._lock:
            self._connection.close()
