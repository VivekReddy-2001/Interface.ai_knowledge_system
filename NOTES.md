# Engineering notes: Phases 1, 2, and 3

The repository provides dataset inspection, validated SQLite ingestion, capture-date
selection, and an evaluator-compatible entry point. It is not a completed knowledge
system. `answer()` selects a capture and deliberately abstains; qualified facts,
effective-date reasoning, conflict resolution, and supported answering remain to be built.

Phase 3a constructs passage and complete Markdown-table evidence units from a
selected stored page version. Units preserve source URLs, snapshot IDs, original
quotes, line ranges, content hashes, headings, and neighboring prose context.
The source quote and enriched search text are separate. Nearby context does not
establish applicability or authority. The inspection command demonstrates construction
on a manually selected URL.

Phase 3b indexes units during ingestion using SQLite FTS5 with BM25. Each snapshot
has its own index so later captures cannot affect historical matches or corpus
statistics. Body/metadata/context weights are 4/2/0.5; stemming is English Porter.
Queries use sanitized quoted tokens with OR matching, deterministic ties, and
capture selection before scoring. A separate CLI exposes ranked evidence; these
hits are not yet converted to member-facing answers. Relevance is not authority.

The engine preserves each complete capture independently using a page primary key
of `(snapshot_id, url)`. It stores original Markdown, separately normalized line
endings, title, crawl timestamp, and content hashes. Snapshot IDs are immutable:
identical replays are safe and changed data under the same ID is rejected. Writes
are transactional. A lock serializes SQLite connection access across the harness's
main ingestion thread and answer worker. Each `build()` uses fresh in-memory storage.
An optional developer command can persist a database under `.local/`.

Without a query date, the newest available capture is selected. Historical queries
use the latest capture on or before the requested date, including dates between
captures. No evidence before the earliest capture causes abstention. Dates after the
last capture use the latest known evidence, not a live confirmation. Removed pages
are not carried forward. Claim effective dates and expired promotions will be
handled by later extraction/resolution stages, separately from capture dates.

Runtime dependencies: Python 3.11 standard library, with SQLite FTS5 enabled. API keys: none.
Development dependencies: pytest and Ruff, pinned in requirements-dev.txt.

The supplied participant kit, website snapshots, generated evidence, and evaluation
results remain under `.local/` and must not be published. The official evaluator
is run unchanged from that local kit. Public smoke tests use synthetic content only.
