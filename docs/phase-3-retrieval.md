# Phase 3b: BM25 candidate retrieval before embeddings

We now search for evidence without supplying a source URL. This is still not a
complete answering system: row/metric selection, effective dates, authority,
conflict resolution, and supported answer construction remain to be implemented.

## Why not embeddings and a vector database yet?

The assignment requires accurate evidence selection, not a particular database or
model. BM25 is a useful baseline because product names, terms, APR/APY labels, and
explicit words appear in both questions and tables. It runs locally and lets us
observe retrieval failures before adding another component.

Embeddings represent meaning as vectors and can improve retrieval when wording
differs substantially. A vector index searches those representations. These are
separate decisions: embeddings do not automatically require a managed database
service. If measured failures justify semantic search, compare it with this baseline
and consider combining both methods.

Neither lexical nor vector similarity determines whether a calculator is stale or
a rate belongs to the requested tier. Both produce candidates needing validation.

## What BM25 does

BM25 rewards matching terms, accounts for how common each term is in the corpus,
limits gains from repetition, and adjusts for document length. It does not generate
answers. We use SQLite FTS5's built-in `bm25()` instead of a new package or a custom
scoring implementation. Python's SQLite must include FTS5; tests check this on the
running environment. No embedding API, credentials, or server is required.

| Indexed column | Content | Initial weight |
|---|---|---:|
| body | Actual passage or complete table | 4.0 |
| metadata | Page title, headings, URL | 2.0 |
| context | Neighboring prose | 0.5 |

These weights are documented engineering defaults, not probabilities or learned
parameters. Giving body text more weight is not a source-authority rule.

## Prepare once, query many times

```text
build() -> SnapshotStore + EvidenceRetriever

ingest(snapshot)
  -> store page versions
  -> construct EvidenceUnit records
  -> build that snapshot's full-text index once

search(question, as_of)
  -> choose an eligible capture
  -> normalize query terms
  -> search that capture's index
  -> return ranked SearchHit records and their original source evidence
```

The official `answer()` still abstains. Index preparation is wired into ingestion,
but factual answering is not yet wired to these hits. The developer CLI exposes
the same retriever separately.

Each snapshot gets a separate FTS5 virtual table. Filtering results from a single
global index would not isolate corpus statistics: future documents could change
historical IDF/length normalization. Separate indexes keep both evidence and scoring
statistics within the selected capture. A regression test verifies this.

Indexes are derived and in-memory. Identical preparation is idempotent, and building
each index is transactional: failed preparation rolls back and can be retried.

## Code walkthrough

1. `SearchHit` in `models.py` combines an evidence unit with a relevance score.
   It is not an `Answer`; its score is not confidence.
2. `query_terms()` splits words/numbers, removes conversational filler, and keeps
   each term once. It does not infer financial qualifiers or interpret dates.
3. `EvidenceRetriever.__init__()` receives the existing store, creates its own
   in-memory SQLite connection, and initializes an index lookup. A lock supports
   main-thread ingestion and worker-thread queries.
4. `prepare()` checks the capture exists and is not already indexed. A generated
   hexadecimal table name prevents supplied IDs from becoming SQL identifiers.
5. `CREATE VIRTUAL TABLE ... USING fts5` creates a full-text index. `UNINDEXED`
   columns retain citation fields and JSON evidence without indexing JSON keys or
   repeated quote text as search terms.
6. `porter unicode61` provides Unicode tokenization and English stemming, allowing
   loan/loans to match. It does not recognize product aliases or convert number words.
7. Each page is parsed, searchable fields are indexed, and the full evidence record
   is serialized as JSON. The ready marker is set only after the transaction commits.
8. `search()` validates the limit, selects a capture, and ensures its index is ready.
   No capture, no useful words, or no matches returns no candidates.
9. Sanitized tokens are quoted, joined with OR, and bound as a parameter. Raw user
   input is not executed as FTS query syntax. Partial matches allow recall; exact
   applicability checks come later.
10. SQLite's BM25 returns negative values with lower being better. We negate them
    for an outward score where higher is better. Scores are not calibrated across
    queries and must not be interpreted as confidence percentages.
11. URL, source line, and unit ID break score ties deterministically. JSON evidence
    is reconstructed into records, restoring heading tuples.
12. `scripts/search_evidence.py` loads the private kit, prepares indexes, times search,
    prints candidates, and saves a private full report. Console previews do not
    truncate stored evidence or source quotes.

## Windows commands

From the repository folder with the virtual environment active:

```cmd
python scripts\search_evidence.py "What was the 10-month fixed jumbo certificate APY?" --as-of 2026-05-31 --top-k 5
python scripts\search_evidence.py "What is the APR for a 60-month auto loan on a 2025 vehicle?" --top-k 5
python -m pytest tests\test_retrieval.py -v
```

Pass `--as-of` explicitly; natural-language dates are not interpreted yet. Reports
with source text remain in `.local/reports/search-results.json` and must not be
published. Each CLI invocation starts a process and rebuilds the indexes. A running
engine prepares them once during ingestion and reuses them for many questions.

## Initial observations and limits

The historical certificate search retrieved a relevant rates table first and the
personal savings table within the top five. Sources repeat tables, so personal,
business, and retirement applicability still needs explicit checks.

On this environment, preparation took about nine seconds, the certificate search
about 0.013 seconds, and search p95 across 40 public questions about 0.085 seconds.
These are development observations, not guarantees for other machines.

Eight public questions in the imported kit have expected-source lists. Four searches
returned a listed URL in their top five. This measures URL matches only, not
supporting-passage recall or answer accuracy. Some alternative sources may be valid;
other results are genuine misses. Inspect mortgage, branch, and link queries before
deciding whether semantic retrieval is the necessary improvement.

An auto-loan query ranked a stale calculator highly: a concrete example of why
relevance does not establish truth. Other current limits include repeated navigation
text, alias coverage, number words, exact tier matching, and source-diverse reranking.

Tests cover relevant tables and citations, future-data isolation including ranking
statistics, removed pages, empty queries, stemming, repeatability, ties, limits,
worker threads, safe query/ID handling, and transactional recovery.

Interview explanation: "I established a local BM25 baseline over source-preserving
evidence units. Separate capture indexes prevent future evidence and future corpus
statistics from influencing historical searches. I evaluate retrieval separately
from final answers and add semantic search only when measured failures justify it."
