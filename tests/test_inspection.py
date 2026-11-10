"""Test inventory checks with synthetic files, never the supplied website."""

import json

from scripts.inspect_snapshots import inspect_snapshot, inspect_snapshots


def write_snapshot(root, name, taken_on, pages):
    folder = root / name
    folder.mkdir()
    entries = []
    for index, (url, text) in enumerate(pages):
        filename = f"page-{index}.md"
        (folder / filename).write_text(text, encoding="utf-8")
        entries.append({"url": url, "file": filename, "title": "Example rates"})
    (folder / "manifest.json").write_text(
        json.dumps({"snapshot_id": name, "taken_on": taken_on, "pages": entries}),
        encoding="utf-8",
    )
    return folder


def test_inventory_orders_by_date_and_distinguishes_changes_from_removals(tmp_path):
    write_snapshot(
        tmp_path,
        "z-old",
        "2026-01-01",
        [("https://example.test/rates", "old"), ("https://example.test/closed", "closed")],
    )
    write_snapshot(
        tmp_path,
        "a-new",
        "2026-02-01",
        [("https://example.test/rates", "new"), ("https://example.test/added", "added")],
    )
    report = inspect_snapshots(tmp_path, ["rates"])
    assert report["snapshot_count"] == 2
    old, new = report["snapshots"]
    assert old["snapshot_id"] == "z-old"
    assert old["changes_from_previous"] is None
    assert new["changes_from_previous"] == {
        "added_urls": ["https://example.test/added"],
        "removed_urls": ["https://example.test/closed"],
        "changed_urls": ["https://example.test/rates"],
    }
    assert len(old["matching_pages"]) == 2  # Both synthetic titles contain "rates".


def test_inventory_reports_duplicate_urls_and_empty_content(tmp_path):
    folder = write_snapshot(
        tmp_path,
        "snapshot",
        "2026-01-01",
        [("https://example.test/rates", ""), ("https://example.test/rates", "text")],
    )
    report, _ = inspect_snapshot(folder, [])
    assert report["duplicate_urls"] == ["https://example.test/rates"]
    assert report["empty_pages"] == ["https://example.test/rates"]


def test_inventory_reports_missing_and_escaping_files(tmp_path):
    folder = write_snapshot(tmp_path, "snapshot", "2026-01-01", [])
    manifest = folder / "manifest.json"
    data = json.loads(manifest.read_text())
    data["pages"] = [
        {"url": "https://example.test/missing", "file": "missing.md"},
        {"url": "https://example.test/escape", "file": "../outside.md"},
    ]
    manifest.write_text(json.dumps(data))
    report, hashes = inspect_snapshot(folder, [])
    assert report["missing_files"] == ["missing.md"]
    assert report["unsafe_files"] == ["../outside.md"]
    assert hashes == {}
