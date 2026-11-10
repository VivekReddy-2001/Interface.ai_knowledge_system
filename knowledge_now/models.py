"""Contract-compatible types for development without the private participant kit."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    markdown: str
    fetched_at: str


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    taken_on: str
    pages: list[Page]


@dataclass
class Source:
    url: str
    snapshot_id: str | None = None
    quote: str | None = None


@dataclass
class Answer:
    text: str
    sources: list[Source] = field(default_factory=list)
    confident: bool = True
    conflict_note: str | None = None


@dataclass
class Conflict:
    topic: str
    values: list[str]
    sources: list[Source]
    resolution: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SnapshotInfo:
    """Small metadata record used to choose a snapshot before loading its pages."""

    snapshot_id: str
    taken_on: str
    page_count: int


@dataclass(frozen=True)
class StoredPage:
    """A page version with original evidence and a separate normalized copy."""

    snapshot_id: str
    url: str
    title: str
    fetched_at: str
    markdown: str
    normalized_markdown: str
    content_hash: str


@dataclass(frozen=True)
class EvidenceUnit:
    """A searchable passage/table that still points back to its original source."""

    unit_id: str
    snapshot_id: str
    url: str
    title: str
    source_hash: str
    kind: Literal["passage", "table"]
    headings: tuple[str, ...]
    start_line: int  # One-based, inclusive source line numbers.
    end_line: int
    text: str  # Normalized passage/table, never an answer synthesized by a model.
    quote: str  # Exact original passage/table, including original line endings.
    context_before: str = ""
    context_after: str = ""

    @property
    def search_text(self) -> str:
        """Add metadata and neighboring context for future ranking, not for quoting."""
        return "\n".join(
            [self.title, *self.headings, self.context_before, self.text, self.context_after]
        )
