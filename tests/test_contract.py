"""A smoke check for a fresh clone, using invented data only."""

from knowledge_now.models import Page, Snapshot
from solution import build


def test_scaffold_runs_and_abstains_without_a_knowledge_index():
    engine = build()
    engine.ingest(
        Snapshot(
            snapshot_id="synthetic-2026-01-01",
            taken_on="2026-01-01",
            pages=[
                Page(
                    url="https://example.test/accounts",
                    title="Example accounts",
                    markdown="Contact the example credit union for account information.",
                    fetched_at="2026-01-01T00:00:00Z",
                )
            ],
        )
    )
    answer = engine.answer("What is the account rate?", as_of="2026-01-01")
    assert answer.text
    assert answer.confident is False
    assert answer.sources == []
    assert isinstance(engine.conflicts(), list)
