"""Inspect unpacked snapshots without modifying the kit or running the engine."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect_snapshot(folder: Path, find: list[str]) -> tuple[dict, dict[str, str]]:
    """Return an inventory and raw-content hashes indexed by source URL."""
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    date.fromisoformat(manifest["taken_on"])
    pages = manifest["pages"]
    counts = Counter(page["url"] for page in pages)
    missing, unsafe, empty, matches = [], [], [], []
    hashes = {}

    for page in pages:
        path = folder / page["file"]
        # A manifest is input data, so do not let a path escape its snapshot.
        if not path.resolve().is_relative_to(folder.resolve()):
            unsafe.append(page["file"])
            continue
        if not path.is_file():
            missing.append(page["file"])
            continue
        raw = path.read_bytes()
        hashes[page["url"]] = hashlib.sha256(raw).hexdigest()
        if not raw.strip():
            empty.append(page["url"])
        searchable = (page["url"] + " " + page.get("title", "")).casefold()
        if any(term.casefold() in searchable for term in find):
            matches.append({"url": page["url"], "title": page.get("title", ""), "file": str(path)})

    report = {
        "snapshot_id": manifest["snapshot_id"],
        "taken_on": manifest["taken_on"],
        "page_count": len(pages),
        "unique_urls": len(counts),
        "duplicate_urls": sorted(url for url, count in counts.items() if count > 1),
        "missing_files": missing,
        "unsafe_files": unsafe,
        "empty_pages": empty,
        "matching_pages": matches,
    }
    return report, hashes


def inspect_snapshots(root: Path, find: list[str]) -> dict:
    folders = [path.parent for path in root.glob("*/manifest.json")]
    if not folders:
        raise ValueError("No unpacked snapshots found. Run scripts/evaluate.py --starter first.")
    inspected = [inspect_snapshot(folder, find) for folder in folders]
    inspected.sort(key=lambda item: (item[0]["taken_on"], item[0]["snapshot_id"]))
    previous = None
    reports = []
    for report, hashes in inspected:
        report["changes_from_previous"] = None
        if previous is not None:
            report["changes_from_previous"] = {
                "added_urls": sorted(hashes.keys() - previous.keys()),
                "removed_urls": sorted(previous.keys() - hashes.keys()),
                "changed_urls": sorted(
                    url for url in hashes.keys() & previous.keys() if hashes[url] != previous[url]
                ),
            }
        reports.append(report)
        previous = hashes
    return {"snapshot_count": len(reports), "snapshots": reports}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, default=ROOT / ".local/kit/snapshots")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/reports/inventory.json")
    parser.add_argument(
        "--find", action="append", default=[], help="Match page URL/title; repeatable"
    )
    args = parser.parse_args()
    try:
        report = inspect_snapshots(args.snapshots, args.find)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for snapshot in report["snapshots"]:
        print(
            f"{snapshot['snapshot_id']}: {snapshot['page_count']} pages; "
            f"missing={len(snapshot['missing_files'])}; "
            f"duplicate URLs={len(snapshot['duplicate_urls'])}; "
            f"unsafe paths={len(snapshot['unsafe_files'])}; "
            f"empty={len(snapshot['empty_pages'])}"
        )
    print(f"Report: {args.out}")
    if any(
        snapshot[key]
        for snapshot in report["snapshots"]
        for key in ("missing_files", "duplicate_urls", "unsafe_files")
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
