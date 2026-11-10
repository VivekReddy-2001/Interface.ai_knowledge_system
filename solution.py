"""Assignment entry point. This scaffold abstains until evidence extraction is built."""

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
        self._snapshots: dict[str, Snapshot] = {}

    def ingest(self, snapshot: Snapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot

    def answer(self, question: str, as_of: str | None = None) -> Answer:
        return Answer(
            text="I don't know. Evidence extraction has not been implemented yet.",
            confident=False,
        )

    def conflicts(self) -> list[Conflict]:
        return []


def build() -> KnowledgeSystem:
    return KnowledgeSystem()
