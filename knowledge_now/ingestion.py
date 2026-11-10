"""Store complete snapshot versions without merging different website captures."""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock

from knowledge_now.models import Snapshot, SnapshotInfo, StoredPage
from knowledge_now.temporal import parse_date, select_snapshot


def normalize_markdown(markdown: str) -> str:
    """Normalize actual line endings only; keep tables, units, footnotes and spacing."""
    return markdown.replace("\r\n", "\n").replace("\r", "\n")


class SnapshotStore:
    def __init__(self, database: str | Path = ":memory:") -> None:
        # The harness ingests on its main thread and answers on a worker thread.
        # Disable SQLite's thread-affinity check, then serialize access with a lock.
        self._lock = Lock()
        self._connection = sqlite3.connect(str(database), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                taken_on TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pages (
                snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                markdown TEXT NOT NULL,
                normalized_markdown TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                PRIMARY KEY (snapshot_id, url)
            );
            """
        )

    def ingest(self, snapshot: Snapshot) -> None:
        """Validate before writing. Identical replays are safe; changed IDs are rejected."""
        if not isinstance(snapshot.snapshot_id, str) or not snapshot.snapshot_id.strip():
            raise ValueError("A snapshot must have a nonempty ID.")
        parse_date(snapshot.taken_on)
        rows = []
        seen_urls = set()
        for page in snapshot.pages:
            if not isinstance(page.url, str) or not page.url.strip():
                raise ValueError("A page must have a nonempty URL.")
            if page.url in seen_urls:
                raise ValueError(f"Duplicate URL within snapshot: {page.url}")
            if not all(isinstance(value, str) for value in (page.title, page.markdown)):
                raise ValueError("Page titles and Markdown must be strings.")
            if not isinstance(page.fetched_at, str):
                raise ValueError("Page fetched_at must be an ISO timestamp string.")
            try:
                # Some harness inputs fall back to an ISO date without a time.
                datetime.fromisoformat(page.fetched_at)
            except ValueError as exc:
                raise ValueError(f"Invalid fetched_at timestamp: {page.fetched_at!r}") from exc
            seen_urls.add(page.url)
            rows.append(
                (
                    snapshot.snapshot_id,
                    page.url,
                    page.title,
                    page.fetched_at,
                    page.markdown,
                    normalize_markdown(page.markdown),
                    hashlib.sha256(page.markdown.encode("utf-8")).hexdigest(),
                )
            )

        rows.sort(key=lambda row: row[1])
        payload = json.dumps([snapshot.taken_on, rows], ensure_ascii=False).encode("utf-8")
        fingerprint = hashlib.sha256(payload).hexdigest()
        # The transaction makes the metadata and page insertions succeed or fail together.
        with self._lock, self._connection:
            previous = self._connection.execute(
                "SELECT fingerprint FROM snapshots WHERE snapshot_id = ?", (snapshot.snapshot_id,)
            ).fetchone()
            if previous is not None:
                if previous["fingerprint"] != fingerprint:
                    raise ValueError(
                        "Snapshot IDs are immutable; use a new ID for changed content."
                    )
                return
            self._connection.execute(
                "INSERT INTO snapshots VALUES (?, ?, ?, ?)",
                (snapshot.snapshot_id, snapshot.taken_on, len(rows), fingerprint),
            )
            self._connection.executemany("INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?, ?)", rows)

    def list_snapshots(self) -> list[SnapshotInfo]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT snapshot_id, taken_on, page_count FROM snapshots "
                "ORDER BY taken_on, snapshot_id"
            ).fetchall()
        return [SnapshotInfo(**dict(row)) for row in rows]

    def select(self, as_of: str | None = None) -> SnapshotInfo | None:
        return select_snapshot(self.list_snapshots(), as_of)

    def pages(self, snapshot_id: str) -> list[StoredPage]:
        """Require a snapshot ID so callers cannot accidentally mix dates."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM pages WHERE snapshot_id = ? ORDER BY url", (snapshot_id,)
            ).fetchall()
        return [StoredPage(**dict(row)) for row in rows]

    def get_page(self, snapshot_id: str, url: str) -> StoredPage | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM pages WHERE snapshot_id = ? AND url = ?", (snapshot_id, url)
            ).fetchone()
        return StoredPage(**dict(row)) if row is not None else None

    def close(self) -> None:
        with self._lock:
            self._connection.close()
