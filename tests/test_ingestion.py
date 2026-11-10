"""Synthetic regression cases for complete, immutable snapshot storage."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from knowledge_now.ingestion import SnapshotStore
from knowledge_now.models import Page, Snapshot
from solution import build


def page(url="https://example.test/rates", text="Example rate table"):
    return Page(url, "Example rates", text, "2026-01-01T00:00:00Z")


@pytest.fixture
def store():
    database = SnapshotStore()
    yield database
    database.close()


def test_versions_and_removed_pages_remain_separate(store):
    old = Snapshot("old", "2026-01-01", [page(text="old"), page("https://example.test/closed")])
    new = Snapshot("new", "2026-02-01", [page(text="new")])
    store.ingest(new)
    store.ingest(old)
    assert [info.snapshot_id for info in store.list_snapshots()] == ["old", "new"]
    assert store.get_page("old", page().url).markdown == "old"
    assert store.get_page("new", page().url).markdown == "new"
    assert store.get_page("new", "https://example.test/closed") is None
    assert len(store.pages("old")) == 2
    assert len(store.pages("new")) == 1


def test_raw_evidence_tables_and_literal_escapes_are_preserved(store):
    raw = "| Term | APR |\r\n| --- | --- |\r\n| 36 months | 8.25%1 |\r\n\\r\\n"
    store.ingest(Snapshot("one", "2026-01-01", [page(text=raw)]))
    stored = store.get_page("one", page().url)
    assert stored.markdown == raw
    assert stored.normalized_markdown == raw.replace("\r\n", "\n")
    assert "8.25%1" in stored.normalized_markdown
    assert stored.normalized_markdown.endswith("\\r\\n")
    assert stored.fetched_at == page().fetched_at
    assert stored.title == page().title


def test_identical_reingestion_is_idempotent_even_if_page_order_changes(store):
    pages = [page(), page("https://example.test/other")]
    store.ingest(Snapshot("one", "2026-01-01", pages))
    store.ingest(Snapshot("one", "2026-01-01", list(reversed(pages))))
    assert len(store.list_snapshots()) == 1
    assert len(store.pages("one")) == 2
    with pytest.raises(ValueError, match="immutable"):
        store.ingest(Snapshot("one", "2026-01-01", [page(text="changed")]))
    assert store.get_page("one", page().url).markdown == page().markdown


@pytest.mark.parametrize(
    "bad",
    [
        Snapshot("duplicate", "2026-01-01", [page(), page()]),
        Snapshot("invalid-date", "2026-02-30", [page()]),
        Snapshot("", "2026-01-01", [page()]),
        Snapshot("invalid-url", "2026-01-01", [page("")]),
        Snapshot("invalid-timestamp", "2026-01-01", [Page("url", "title", "text", "yesterday")]),
    ],
)
def test_invalid_capture_does_not_partially_write(store, bad):
    store.ingest(Snapshot("good", "2026-01-01", [page()]))
    with pytest.raises(ValueError):
        store.ingest(bad)
    assert [info.snapshot_id for info in store.list_snapshots()] == ["good"]
    assert store.pages(bad.snapshot_id) == []


def test_empty_snapshot_is_a_complete_view(store):
    store.ingest(Snapshot("old", "2026-01-01", [page()]))
    store.ingest(Snapshot("empty", "2026-02-01", []))
    assert store.select().page_count == 0
    assert store.pages(store.select().snapshot_id) == []


def test_explicit_disk_storage_can_be_reopened(tmp_path):
    path = tmp_path / "evidence.sqlite"
    first = SnapshotStore(path)
    first.ingest(Snapshot("one", "2026-01-01", [page()]))
    first.close()
    second = SnapshotStore(path)
    try:
        assert second.select().snapshot_id == "one"
        assert second.get_page("one", page().url).markdown == page().markdown
    finally:
        second.close()


def test_database_failure_rolls_back_snapshot_and_earlier_page_inserts(tmp_path):
    path = tmp_path / "evidence.sqlite"
    store = SnapshotStore(path)
    try:
        # Inject a real SQLite write failure after a valid page has been inserted.
        with sqlite3.connect(path) as connection:
            connection.executescript(
                """
                CREATE TRIGGER reject_example BEFORE INSERT ON pages
                WHEN NEW.url = 'https://example.test/z-reject'
                BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END;
                """
            )
        with pytest.raises(sqlite3.IntegrityError, match="synthetic write failure"):
            store.ingest(
                Snapshot(
                    "failed",
                    "2026-01-01",
                    [page("https://example.test/a-valid"), page("https://example.test/z-reject")],
                )
            )
        assert store.list_snapshots() == []
        assert store.pages("failed") == []
        store.ingest(Snapshot("recovered", "2026-01-01", [page()]))
        assert store.select().snapshot_id == "recovered"
    finally:
        store.close()


def test_fresh_engines_are_isolated_and_worker_thread_answering_works():
    engine = build()
    engine.ingest(Snapshot("one", "2026-01-01", [page()]))
    with ThreadPoolExecutor(max_workers=1) as pool:
        answer = pool.submit(engine.answer, "What is the rate?", "2026-01-01").result()
    assert answer.confident is False  # Retrieval has not been implemented.
    assert "extraction" in answer.text
    assert "No snapshot" in build().answer("What is the rate?").text
    assert "No snapshot" in engine.answer("What is the rate?", "2025-12-31").text
    assert "valid date" in engine.answer("What is the rate?", "invalid").text
