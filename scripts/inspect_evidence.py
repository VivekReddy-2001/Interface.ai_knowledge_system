"""Inspect evidence units from one stored page; this is not ranked question answering."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", required=True, help="A source URL from the local snapshot inventory"
    )
    parser.add_argument("--as-of", help="Optional historical cutoff in YYYY-MM-DD format")
    parser.add_argument("--kind", choices=["passage", "table"], help="Optional unit type filter")
    parser.add_argument("--contains", help="Optional literal substring filter on unit text")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/reports/evidence-units.json")
    args = parser.parse_args()
    harness = ROOT / ".local/kit/harness"
    if not (harness / "run_eval.py").is_file():
        parser.error("Import the participant kit with scripts/import_kit.py first.")
    sys.path.insert(0, str(harness))
    sys.path.insert(0, str(ROOT))
    from run_eval import load_snapshots

    from knowledge_now.ingestion import SnapshotStore
    from knowledge_now.parsing import build_evidence_units

    store = SnapshotStore()
    try:
        for snapshot in load_snapshots(ROOT / ".local/kit/snapshots"):
            store.ingest(snapshot)
        selected = store.select(args.as_of)
        if selected is None:
            parser.error("No snapshot is available on or before the requested date.")
        page = store.get_page(selected.snapshot_id, args.url)
        if page is None:
            parser.error("That URL does not exist in the selected snapshot.")
        units = build_evidence_units(page)
        total = len(units)
        if args.kind:
            units = [unit for unit in units if unit.kind == args.kind]
        if args.contains:
            units = [unit for unit in units if args.contains.casefold() in unit.text.casefold()]
        report = {
            "snapshot": asdict(selected),
            "url": page.url,
            "total_page_units": total,
            "selected_units": [asdict(unit) for unit in units],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Selected snapshot: {selected.snapshot_id}")
        print(f"Page: {page.url}")
        print(f"Page units: {total}; matching units: {len(units)}")
        for unit in units:
            print(f"\n{unit.kind}: lines {unit.start_line}-{unit.end_line}")
            print(unit.text.rstrip())
        print(f"\nPrivate report: {args.out}")
        print("These are candidate evidence units, not a resolved member-facing answer.")
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        store.close()


if __name__ == "__main__":
    main()
