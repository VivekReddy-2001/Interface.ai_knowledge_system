"""Check relevance and isolation with synthetic evidence, not practice answers."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from knowledge_now.ingestion import SnapshotStore
from knowledge_now.models import Page, Snapshot
from knowledge_now.retrieval import EvidenceRetriever, query_terms


@pytest.fixture
def system():
    store = SnapshotStore()
    retriever = EvidenceRetriever(store)
    yield store, retriever
    retriever.close()
    store.close()


def page(path, title, text):
    return Page("https://example.test/" + path, title, text, "2026-01-01")


def test_ranks_qualified_table_and_preserves_exact_citation(system):
    store, retriever = system
    table = "Term | APY\n--- | ---\n9-month jumbo certificate | 3.20%\n"
    store.ingest(
        Snapshot(
            "one",
            "2026-01-01",
            [
                page("savings", "Certificate accounts", "# Certificates\n\n" + table),
                page("mortgages", "Home loans", "Thirty-year mortgage APR details."),
                page("cards", "Payment cards", "Credit card APR details."),
            ],
        )
    )
    hits = retriever.search("What is the nine month jumbo certificate APY?", top_k=2)
    assert hits[0].unit.url.endswith("/savings")
    assert hits[0].unit.kind == "table"
    assert hits[0].unit.quote == table
    assert hits[0].unit.headings == ("Certificates",)
    assert hits[0].score > 0
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)


def test_snapshot_filter_applies_to_results_and_ranking_statistics(system):
    store, retriever = system
    store.ingest(
        Snapshot("old", "2026-01-01", [page("rates", "Certificate", "Jumbo certificate APY.")])
    )
    before = retriever.search("jumbo certificate", "2026-01-31")
    store.ingest(
        Snapshot("new", "2026-02-01", [page("rates", "Future", "FutureOnly jumbo jumbo.")])
    )
    retriever.prepare("new")
    after = retriever.search("jumbo certificate", "2026-01-31")
    assert before == after
    assert retriever.search("FutureOnly", "2026-01-31") == []
    assert retriever.search("FutureOnly")[0].unit.snapshot_id == "new"
    assert retriever.search("jumbo", "2025-12-31") == []


def test_removed_page_cannot_leak_into_current_search(system):
    store, retriever = system
    store.ingest(Snapshot("old", "2026-01-01", [page("closed", "Branch", "Oldtown lobby hours.")]))
    store.ingest(Snapshot("new", "2026-02-01", []))
    assert retriever.search("Oldtown lobby") == []
    assert retriever.search("Oldtown lobby", "2026-01-15")[0].unit.snapshot_id == "old"


def test_no_evidence_or_no_matching_terms_returns_no_candidates(system):
    store, retriever = system
    assert retriever.search("loan") == []
    store.ingest(Snapshot("one", "2026-01-01", [page("rates", "Rates", "Loan APR details.")]))
    for query in ("", "!!!", "what is the", "xylophonenebula"):
        assert retriever.search(query) == []
    with pytest.raises(ValueError):
        retriever.search("loan", "invalid-date")
    with pytest.raises(ValueError, match="positive"):
        retriever.search("loan", top_k=0)


def test_stemming_repeated_preparation_determinism_and_tie_breaking(system):
    store, retriever = system
    store.ingest(
        Snapshot(
            "one",
            "2026-01-01",
            [
                page("b", "Borrowing", "Loan APR details."),
                page("a", "Borrowing", "Loan APR details."),
            ],
        )
    )
    first = retriever.search("loans")
    retriever.prepare("one")
    assert retriever.search("loans") == first
    assert len(first) == 2
    assert first[0].unit.url.endswith("/a")
    assert len(retriever.search("loans", top_k=1)) == 1
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(retriever.search, "loans").result() == first


def test_query_syntax_and_snapshot_ids_are_treated_as_data(system):
    store, retriever = system
    snapshot_id = 'odd"; DROP TABLE pages; --'
    store.ingest(Snapshot(snapshot_id, "2026-01-01", [page("rates", "Loans", "Loan APR details.")]))
    hits = retriever.search('"loan" OR ) NOT * :')
    assert hits[0].unit.snapshot_id == snapshot_id
    assert len(store.pages(snapshot_id)) == 1
    assert query_terms("WHAT is the 60-month loan APR?") == ["60", "month", "loan", "apr"]
    assert query_terms("loan LOAN loan") == ["loan"]
    with pytest.raises(ValueError, match="Unknown snapshot"):
        retriever.prepare("missing")


def test_failed_preparation_rolls_back_and_can_be_retried(system, monkeypatch):
    store, retriever = system
    store.ingest(
        Snapshot(
            "one",
            "2026-01-01",
            [page("a", "Loans", "Loan APR."), page("b", "Loans", "Loan APR.")],
        )
    )
    import knowledge_now.retrieval as module

    original = module.build_evidence_units
    failing = [True]

    def fail_second_page(stored_page):
        if failing[0] and stored_page.url.endswith("/b"):
            raise ValueError("synthetic parse failure")
        return original(stored_page)

    monkeypatch.setattr(module, "build_evidence_units", fail_second_page)
    with pytest.raises(ValueError, match="synthetic parse failure"):
        retriever.prepare("one")
    failing[0] = False
    assert len(retriever.search("loan APR")) == 2
