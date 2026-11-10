# Phase 3a: what retrieval will search

This is the evidence-unit layer, the first part of retrieval. The parser does not
rank evidence or decide what is true. The subsequent [BM25 layer](phase-3-retrieval.md)
now searches these units automatically. `answer()` continues to abstain while
financial interpretation and resolution are being built.

## Where the text comes from

```text
Supplied Markdown files
  -> official harness creates Snapshot/Page objects
  -> our ingest() stores each page version in SQLite
  -> temporal selection chooses one snapshot
  -> store.get_page(snapshot_id, url) returns a StoredPage
  -> build_evidence_units(page) returns passages and tables
  -> future retrieval ranks units within that snapshot
```

There are no live website calls. A source URL identifies an already stored page;
passing that URL to the inspection command does not download it from the internet.

## What an evidence unit contains

It is a piece of source content that can be searched and traced back to its origin.
It is neither an extracted financial fact nor a final answer. A whole rate table
can contain several products and values; later code must select the applicable row
and metric before producing a member-facing response.

| Field | Why we retain it |
|---|---|
| `unit_id` | A repeatable hash of source identity, version, and line span. |
| `snapshot_id` | Keep different captures separate. |
| `url`, `title` | Identify the source and help future ranking. |
| `source_hash` | Identify the original page content version. |
| `kind` | Distinguish a prose passage from a table. |
| `headings` | Retain the surrounding ATX Markdown heading hierarchy. |
| `start_line`, `end_line` | Locate the quote in the original page. |
| `text` | Normalized source content to search; tables retain all headers/rows. |
| `quote` | Exact original source slice, including original line endings. |
| `context_before`, `context_after` | Up to two neighboring prose blocks on each side. |
| `search_text` | A computed combination of title, headings, content, and context. |

Quote and search text are deliberately separate. Nearby notes help find evidence
but are not part of the unit's verbatim quote. Context is a clue, not proof that a
date or condition applies to every row. Neighboring passages remain separate units.

## Why preserve complete tables?

Consider this invented example:

```text
| Product | Dividend Rate | APY | Minimum |
| --- | --- | --- | --- |
| 9-month jumbo special | 3.15% | 3.20%1 | $90,000 |
| 9-month standard special | 3.05% | 3.10%2 | $900 |
```

An isolated `3.20%` loses its product, term, metric, and eligibility. The complete
table retains those relationships. Footnote digits remain unchanged; interpreting
them is a later financial-parsing task. No fixed character limit cuts off table
rows. Later we can add row-level units that repeat headers and link to their table.

## Run it in Windows Command Prompt

From the project folder, with the virtual environment activated:

```cmd
python scripts\inspect_evidence.py --url https://www.dupaco.com/personal/savings-account --as-of 2026-05-31 --kind table --contains "10 Month"
python -m pytest tests\test_parsing.py -v
```

This command manually specifies the page we found in the earlier exercise. It
loads the supplied captures, stores them in memory, selects May 19, gets the stored
page, and constructs its evidence units. `--contains` is a literal text filter for
inspection, not BM25 or semantic search. Ranked retrieval will later discover
sources without requiring the user to supply a URL.

The relevant table is at lines 417-422 of that captured page. The generated
`.local/reports/evidence-units.json` retains context and provenance. Filters limit
the displayed units; the parser still processes the whole selected page. Do not
commit this private report or the supplied website text.

## Code reading order

Start at `EvidenceUnit` in `knowledge_now/models.py`:

1. `@dataclass(frozen=True)` defines an immutable record. Python generates its
   constructor and useful equality/repr behavior. Fields cannot be reassigned.
2. `Literal["passage", "table"]` documents allowed kinds for type checking.
   Annotations alone do not enforce runtime validation.
3. `tuple[str, ...]` represents an immutable sequence of heading labels.
4. `@property` makes `search_text` look like a field while computing its value.
   It combines existing strings; it does not generate new financial information.

Then follow `knowledge_now/parsing.py`:

1. Compiled regular expressions recognize headings, code fences, and table
   separator cells. `_Block` represents an internal zero-based line slice.
2. `_cells()` splits unescaped pipes and trims cell boundaries. Optional outer
   pipes do not create extra columns. Escaped pipes stay inside their cells.
3. `_starts_table()` requires a header followed by a same-width separator row,
   with at least two cells. A random prose line containing a pipe is not enough.
4. `_blocks()` walks the page with an index. Blank lines separate passages.
   Headings update the hierarchy: a sibling replaces the previous sibling while
   retaining higher-level ancestors.
5. Fenced code stays whole as a passage. Its internal headings and pipe characters
   do not become document structure. Actual tables retain all contiguous rows.
   A new table, heading, or code fence ends the preceding table.
6. Other content forms passages until a blank line or new structural block.
   Navigation and repeated text are retained; ranking/filtering comes later.
7. `_neighbor_context()` collects up to two adjacent passages in source order,
   stopping at headings or tables. Plain labels can therefore accompany a table
   even if they were not written as Markdown headings.
8. `build_evidence_units()` uses normalized lines for parsing and original lines
   for quotes. `keepends=True` retains line endings. A line-count mismatch fails
   rather than producing misleading source offsets.
9. A heading with a body/subsection becomes context on that evidence. A heading
   without a body becomes a passage so its information is still searchable.
10. A hash of snapshot, URL, source content, and offsets identifies each unit.
    Duplicate passages at different source locations still have distinct IDs.
11. Each unit receives normalized text and its exact original quote. Python's
    slice `[2:5]` maps to one-based inclusive source lines 3 through 5.

Leading underscores indicate private helper names by convention. Later retrieval
can call `build_evidence_units()` without depending on the block parser's details.

## Tests and limits

Synthetic tests check table integrity, context, CRLF quotes, fenced examples,
escaped pipes, heading scope, adjacent tables, long tables, repeatable IDs, distinct
versions, empty pages, source offsets, and capture isolation. The supplied corpus
is also checked locally for exact quote slices without publishing its contents.

This small parser is not a full CommonMark renderer. HTML tables, complex nested
tables, and alternate heading syntax have no special treatment. Unrecognized text
is retained as passages. The parser returns units in memory; the separate BM25 layer
indexes them during ingestion. Nearby context is not a resolved applicability rule.

Continue with the [BM25 retrieval walkthrough](phase-3-retrieval.md). A high relevance
score still requires qualifier matching, effective-date analysis, and conflict
resolution before producing an answer.

Interview explanation: "I retrieve from supplied, versioned website evidence. I
construct passages and intact financial tables with source identity, heading
context, and exact quotes. Temporal filtering defines the search corpus before
ranking; relevance alone does not establish correctness."
