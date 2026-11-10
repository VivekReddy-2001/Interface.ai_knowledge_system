"""Demonstrate ingestion and date selection using the unchanged local kit loader."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="Select the latest capture on/before YYYY-MM-DD")
    parser.add_argument("--url", help="Inspect one source URL within the selected capture")
    parser.add_argument("--database", type=Path, help="Optional SQLite file; defaults to memory")
    args = parser.parse_args()
    harness = ROOT / ".local/kit/harness"
    if not (harness / "run_eval.py").is_file():
        parser.error("Import the participant kit with scripts/import_kit.py first.")
    # This developer command reuses the kit's loader. The engine itself receives objects.
    sys.path.insert(0, str(harness))
    sys.path.insert(0, str(ROOT))
    from run_eval import load_snapshots

    from knowledge_now.ingestion import SnapshotStore

    if args.database:
        args.database.parent.mkdir(parents=True, exist_ok=True)
    store = SnapshotStore(args.database if args.database else ":memory:")
    try:
        for snapshot in load_snapshots(ROOT / ".local/kit/snapshots"):
            store.ingest(snapshot)
            print(f"Stored {snapshot.snapshot_id}: {len(snapshot.pages)} pages")
        selected = store.select(args.as_of)
        if selected is None:
            print("No snapshot is available for the requested date.")
            return
        print(f"Selected {selected.snapshot_id}: {selected.page_count} pages")
        if args.url:
            page = store.get_page(selected.snapshot_id, args.url)
            if page is None:
                print("That URL does not exist in the selected snapshot.")
            else:
                print(
                    json.dumps(
                        {
                            "url": page.url,
                            "title": page.title,
                            "fetched_at": page.fetched_at,
                            "content_hash": page.content_hash,
                            "raw_characters": len(page.markdown),
                            "normalized_characters": len(page.normalized_markdown),
                        },
                        indent=2,
                    )
                )
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        store.close()


if __name__ == "__main__":
    main()
