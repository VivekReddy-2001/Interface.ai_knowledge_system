"""Search supplied captures for candidate evidence without generating a financial answer."""

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Question or keywords; enclose in quotes")
    parser.add_argument("--as-of", help="Optional capture cutoff in YYYY-MM-DD format")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--out", type=Path, default=ROOT / ".local/reports/search-results.json")
    args = parser.parse_args()
    harness = ROOT / ".local/kit/harness"
    if not (harness / "run_eval.py").is_file():
        parser.error("Import the participant kit with scripts/import_kit.py first.")
    sys.path.insert(0, str(harness))
    sys.path.insert(0, str(ROOT))
    from run_eval import load_snapshots

    from knowledge_now.ingestion import SnapshotStore
    from knowledge_now.retrieval import EvidenceRetriever

    store = SnapshotStore()
    retriever = EvidenceRetriever(store)
    try:
        started = time.perf_counter()
        for snapshot in load_snapshots(ROOT / ".local/kit/snapshots"):
            store.ingest(snapshot)
            retriever.prepare(snapshot.snapshot_id)
        preparation_s = time.perf_counter() - started
        started = time.perf_counter()
        hits = retriever.search(args.question, args.as_of, args.top_k)
        search_s = time.perf_counter() - started
        selected = store.select(args.as_of)
        report = {
            "question": args.question,
            "snapshot": asdict(selected) if selected else None,
            "preparation_seconds": round(preparation_s, 3),
            "search_seconds": round(search_s, 4),
            "hits": [asdict(hit) for hit in hits],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Snapshot: {selected.snapshot_id if selected else 'none available'}")
        print(f"Preparation: {preparation_s:.2f}s; search: {search_s:.4f}s")
        for rank, hit in enumerate(hits, start=1):
            unit = hit.unit
            print(f"\n{rank}. score={hit.score:.4f}; {unit.kind}; {unit.url}")
            print(f"Source lines {unit.start_line}-{unit.end_line}")
            print(unit.text[:800].rstrip())
        print(f"\nPrivate full results: {args.out}")
        print("Scores measure word relevance, not truth or answer confidence.")
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        retriever.close()
        store.close()


if __name__ == "__main__":
    main()
