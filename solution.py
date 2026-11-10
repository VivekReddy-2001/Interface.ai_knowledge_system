"""Assignment entry point. This scaffold abstains until evidence extraction is built."""

from knowledge_now.ingestion import SnapshotStore
from knowledge_now.retrieval import EvidenceRetriever

try:
    # The official evaluator provides this module on its import path.
    from contract import Answer, Conflict, Snapshot
except ModuleNotFoundError as exc:
    if exc.name != "contract":
        raise
    from knowledge_now.models import Answer, Conflict, Snapshot


class KnowledgeSystem:
    """Keep snapshots separately so later work can support historical queries."""

    def __init__(self) -> None:
        self._store = SnapshotStore()
        self._retriever = EvidenceRetriever(self._store)

    def ingest(self, snapshot: Snapshot) -> None:
        self._store.ingest(snapshot)
        self._retriever.prepare(snapshot.snapshot_id)

    def answer(self, question: str, as_of: str | None = None) -> Answer:
        try:
            snapshot = self._store.select(as_of)
        except ValueError:
            return Answer(text="Please provide a valid date in YYYY-MM-DD format.", confident=False)
        if snapshot is None:
            return Answer(
                text="I don't know. No snapshot is available for that date.", confident=False
            )
        return Answer(
            text="I don't know. Evidence extraction has not been implemented yet.",
            confident=False,
        )

    def conflicts(self) -> list[Conflict]:
        return []


def build() -> KnowledgeSystem:
    return KnowledgeSystem()
