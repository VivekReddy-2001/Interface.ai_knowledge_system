# Phase 2: store evidence and select the correct capture

This phase implements snapshot storage and capture-date selection. Retrieval,
financial fact extraction, effective-date reasoning, and conflict resolution remain
future work. Answering still abstains even after a snapshot has been selected.

## Run and inspect

From the repository folder with the virtual environment activated:

```cmd
python scripts\check_ingestion.py
python scripts\check_ingestion.py --as-of 2026-05-31
python scripts\check_ingestion.py --as-of 2026-05-01
python scripts\check_ingestion.py --database .local\evidence.sqlite --as-of 2026-05-31
python -m pytest tests\test_ingestion.py tests\test_temporal.py -v
python scripts\evaluate.py
```

The first command selects September 28. The second selects May 19. The third
reports that no capture is available. A date after the final capture uses the
latest available evidence; it does not establish what the live website says then.
You can add `--url "<a source URL from your inventory>"` to inspect page metadata.

The optional database file stays under `.local/`. The official engine uses a fresh
in-memory database on every `build()` call, keeping separate runs isolated.

## What each new file does

| File | Responsibility |
|---|---|
| `knowledge_now/ingestion.py` | Validate supplied objects, store immutable capture/page versions, return stored evidence. |
| `knowledge_now/temporal.py` | Parse strict ISO calendar dates and choose an eligible capture. |
| Additions to `models.py` | `SnapshotInfo` is small capture metadata; `StoredPage` carries raw and normalized evidence. |
| `scripts/check_ingestion.py` | Reuse the kit's loader to demonstrate storage and date selection locally. |
| `tests/test_ingestion.py` | Check version isolation, normalization, replay behavior, transactions, persistence, and worker-thread access. |
| `tests/test_temporal.py` | Check boundaries, invalid dates, ordering, and deterministic same-date ties. |

`solution.py` now delegates ingestion to the store. Its `answer()` selects a capture
first, then abstains because evidence extraction is not implemented. It separately
handles an invalid date and the absence of any eligible capture.

## Why SQLite, and why two tables?

Python includes `sqlite3`; there is no server or new package to install. SQL queries
explicitly scope page reads to a snapshot. We keep the architecture simple while
preparing for later evidence retrieval.

```text
snapshots
  snapshot_id [primary key]
  taken_on
  page_count
  fingerprint

pages
  snapshot_id [foreign key to snapshots]
  url
  title
  fetched_at
  markdown
  normalized_markdown
  content_hash
  [primary key: snapshot_id + url]
```

The composite primary key means a URL can appear once per snapshot and can have
different contents in different snapshots. Removing a page in a later capture does
not delete its historical version and does not carry it into the current capture.

## Walk through ingestion.py

1. Imports supply SHA-256 hashing, JSON serialization, SQLite, timestamp validation,
   paths, and a thread lock. Models define the records we return; temporal helpers
   validate capture dates and select evidence.
2. `normalize_markdown()` replaces actual CRLF/CR line endings with LF. It does not
   flatten tables, strip footnotes, collapse spaces, or decode literal `\\r\\n` text.
   The untouched original is stored separately for provenance.
3. `SnapshotStore.__init__()` opens a database. `:memory:` is SQLite's special
   in-memory database name. An explicit path is supported by the developer command.
4. The official harness writes from the main thread and answers on a worker.
   `check_same_thread=False` permits this. `Lock()` serializes our connection use;
   disabling the thread check alone would not be a concurrency strategy.
5. `sqlite3.Row` lets us access query results by column name. `PRAGMA foreign_keys`
   enables parent-child integrity. The schema is created if it does not exist.
6. `ingest()` checks the snapshot ID and capture date. It builds rows in memory
   before changing the database, rejecting duplicate source URLs and malformed
   input. A date-only fetched timestamp is accepted because the kit loader can
   fall back to the capture date.
7. Each row retains the original URL, title, timestamp, raw text, normalized text,
   and a hash of the original Markdown. Empty text is retained as missing evidence,
   rather than replaced with another capture's content.
8. Rows are sorted by URL. JSON serialization of the date and records is hashed
   into a capture fingerprint. Reordering input pages does not change that hash.
9. `with self._lock, self._connection` acquires the lock and starts a transaction
   scope. Successful writes commit; an exception rolls them back together.
10. A previously seen ID with an identical fingerprint is an idempotent replay:
    ingestion returns without inserting duplicates. Different data under the same
    ID is rejected; a new capture must get a new ID. Metadata changes count too.
11. `?` placeholders bind values as data rather than assembling executable SQL
    from page contents. The parent row and all page rows are inserted together.
12. `list_snapshots()` returns small metadata records in date order. `select()`
    passes those records to the pure date-selection function.
13. `pages()` requires a snapshot ID. `get_page()` requires both an ID and URL.
    These interfaces make date scoping explicit, avoiding accidental cross-date
    searches. Rows are converted into `StoredPage` records outside the lock.
14. `close()` releases the database connection. The demonstration command and store
    tests call it when finished. The engine owns its connection for its lifetime.

The store accepts out-of-order calls and lists/selects by date, even though the
official harness already supplies captures chronologically.

## Walk through temporal.py

`parse_date()` first requires a string. `date.fromisoformat()` rejects impossible
calendar dates; comparing `isoformat()` with the original rejects alternative
representations such as compact `YYYYMMDD`. The public input format is YYYY-MM-DD.

`select_snapshot()` turns `as_of` into a cutoff date. The list comprehension keeps
only captures on or before it. `max(..., default=None)` selects the latest eligible
capture, or returns `None` when there is none. Without a cutoff all captures are
eligible. The ID is a stable tie-breaker for same-day captures; the supplied data
has one capture per date, so this is not a claim about within-day recency.

Capture date selection is different from deciding whether a promotion expired or
which table's effective date applies. Those require qualified facts and come later.

## Walk through solution.py's integration

`build()` still creates one engine. `__init__()` now creates its `SnapshotStore`.
The public `ingest()` forwards a supplied object to the store; it does not open ZIPs
or read files. The official harness handles that boundary.

`answer()` asks the store to select a capture. Invalid dates and unavailable
history return an unconfident answer. A valid capture currently reaches the
explicit extraction-not-implemented response. `conflicts()` still returns `[]`.

The contract import/fallback remains unchanged. The engine accepts official objects
by their fields; it does not require `isinstance` against our local model classes.

## What the tests prove

- Separate versions of the same URL stay separate, including removed pages.
- Original text is unchanged and normalization preserves table values/qualifiers.
- Identical ingestion does not duplicate data; changed immutable IDs fail.
- Validation failure leaves existing evidence unchanged.
- An injected SQLite write failure rolls back metadata and earlier page inserts.
- Empty captures do not fall back to old pages.
- An explicitly saved database can be reopened.
- Fresh engines do not share state, and the harness's worker-thread pattern works.
- Date selection handles exact dates, gaps, earlier/later dates, and malformed input.

No knowledge-answering accuracy improvement is expected in this phase. The official
public run remains at 0.093 because it correctly abstains on refusal cases; retrieval
and factual answering are still absent. This equals the starter's aggregate score
for different reasons and should not be interpreted as equivalent behavior.

## Debugging and interview practice

Use **Debug public evaluation** in VS Code. Break at `build()`, the beginning of
`SnapshotStore.ingest()`, and `snapshot = self._store.select(as_of)` in `answer()`.
Build runs once, ingestion runs five times, and selection repeats for each question.

In the Debug Console after ingestion, inspect:

```python
self._store.list_snapshots()
self._store.select("2026-05-31")
```

Interview explanation: "I store complete captures with a composite page key of
snapshot ID and URL. I retain raw provenance, use transactions and idempotent
ingestion, and scope queries to the last available capture before the requested
date. This prevents future evidence and removed pages from leaking into historical
or current answers."

Next: create provenance-preserving sections/table rows for retrieval. Do not use
raw word overlap to declare which financial claim is authoritative.
