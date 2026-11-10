# Initial engineering notes

This repository currently provides the development setup and evaluator-compatible
entry point. It is not a completed knowledge system. `answer()` deliberately abstains;
fact extraction, retrieval, temporal selection, and conflict resolution remain to be built.

The planned engine preserves each complete website snapshot independently. Queries
without a date will use the newest supplied snapshot. Historical queries will use
the latest supplied snapshot on or before the requested date. Snapshot capture dates
and dates when claims take effect will be represented separately. Source authority
and product qualifiers will inform conflict resolution.

Initial runtime dependencies: Python 3.11 standard library only. API keys: none.
Development dependencies: pytest and Ruff, pinned in requirements-dev.txt.

The supplied participant kit, website snapshots, generated evidence, and evaluation
results remain under `.local/` and must not be published. The official evaluator
is run unchanged from that local kit. Public smoke tests use synthetic content only.
