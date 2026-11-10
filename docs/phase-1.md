# Phase 1: understand the input before building the engine

The environment and starter baseline already existed. This phase adds an inventory
tool and inspects the input format. No question-answering logic is implemented here.

## Run it on Windows

From the repository folder, with the virtual environment activated:

```cmd
python scripts\inspect_snapshots.py --find auto-motorcycle-loans --find savings-account --find home-loans --find contact --find construction
```

If the kit has not been unpacked, first run `python scripts\evaluate.py --starter`.
The inspection command reads local files only. It writes
`.local/reports/inventory.json`, which must remain out of public GitHub.
Open that JSON file in VS Code; `matching_pages` gives paths to representative pages.
`--find` searches URL/title metadata, not the entire page text.

## What the real inventory found

| Capture date | Pages | Missing files | Duplicate URLs | Empty pages |
|---|---:|---:|---:|---:|
| May 12, 2026 | 637 | 0 | 0 | 0 |
| May 19, 2026 | 634 | 0 | 0 | 0 |
| June 9, 2026 | 635 | 0 | 0 | 0 |
| August 27, 2026 | 683 | 0 | 0 | 0 |
| September 28, 2026 | 705 | 0 | 0 | 0 |

There are 3,294 page records across the captures. These are not 3,294 unique URLs:
the same URL can have a different version in each snapshot. No unsafe file paths
were found in this supplied dataset.

| Compared with previous capture | Added URLs | Removed URLs | Raw content changed |
|---|---:|---:|---:|
| May 19 | 1 | 4 | 615 |
| June 9 | 9 | 8 | 611 |
| August 27 | 50 | 2 | 623 |
| September 28 | 25 | 3 | 259 |

Hashes compare raw file bytes. A changed hash can reflect navigation, related
articles, formatting, or a real factual update. It is not proof of a contradiction.

## How to explore five representative topics

For each topic, follow a matching URL through all five manifests. Read its heading,
table headers, rows, footnotes, and dates together. Keep detailed notes/excerpts in
`.local/reports/`; this document publishes only aggregate observations.

| Topic | Observation | Consequence for our design |
|---|---|---|
| Auto loans | Product and calculator pages can disagree; eligibility ranges also change. | Compare overlapping vehicle eligibility and identical terms, not arbitrary rates. |
| Certificates | Dividend rate and APY occupy separate columns; standard and jumbo differ. | Preserve column meanings and product qualifiers. |
| Mortgages | Purchase/refinance tables and loan-amount tiers can repeat similar numbers. | A percentage alone is not a complete fact. |
| Branches | Locator pages mix owned branches, ATMs, and other institutions; closure announcements carry event dates. | Preserve entity context and distinguish event dates from crawl dates. |
| Unpublished construction rate | Product descriptions contain percentages for financing/down payments without publishing a loan APR. | A nearby number is not automatically the requested rate. |

Other input details: some financial values have attached footnote digits; pages
contain Unicode dashes and spaces; some text contains literal escaped newline
sequences. These need deliberate treatment during parsing, not broad replacements
that silently alter the evidence.

## Read scripts/inspect_snapshots.py in this order

1. The module docstring explains the script's purpose. Imports provide command-line
   parsing, hashing, JSON, duplicate counting, dates, and filesystem paths.
2. `ROOT` finds the repository from this script's location, so default input/output
   paths do not depend on which folder launched Python.
3. `inspect_snapshot()` reads one manifest. `json.loads()` converts JSON text into
   Python dictionaries/lists. `date.fromisoformat()` checks its calendar date.
4. `Counter(...)` counts occurrences of each URL. Counts above one indicate a
   duplicate within that capture, rather than the normal reuse across captures.
5. The loop resolves each manifest path and checks it remains inside the snapshot.
   `continue` skips an unsafe or missing file while recording the problem.
6. `read_bytes()` preserves the exact original file representation. SHA-256 gives
   us a content fingerprint; the hash is not an embedding or a semantic summary.
7. `raw.strip()` detects files containing only whitespace. `casefold()` allows
   case-insensitive metadata matching. Matches retain the source and local path.
8. The returned tuple contains a readable report plus URL-to-hash lookup data.
9. `inspect_snapshots()` discovers manifests and sorts captures by metadata date.
   It does not assume folder names happen to sort correctly.
10. Set differences find added/removed readable URLs. Shared URLs with different
    hashes are recorded separately. The first capture has no predecessor.
11. `main()` defines command-line arguments, calls the inspection functions, writes
    the report, and prints a short summary. Problems produce a nonzero exit code.
12. The `if __name__ == "__main__"` guard runs the CLI only when this file is
    executed directly. Importing the functions in tests does not run the CLI.

The synthetic tests cover date ordering, changed/removed pages, duplicate URLs,
empty content, missing files, and escaping paths. They do not distribute website data.

## Debugging exercise

Set a breakpoint on `manifest = json.loads(...)`, then step through one page.
Inspect `manifest`, `page`, `path`, `raw`, and `hashes`. Observe that the manifest
contains metadata and filenames; the Markdown file contains the actual evidence.

Interview explanation: "I began with an inventory of the supplied complete website
captures. I verified file integrity and compared URL membership and content hashes,
while keeping factual changes distinct from ordinary formatting changes."
