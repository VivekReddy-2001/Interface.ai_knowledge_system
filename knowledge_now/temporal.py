"""Select available evidence by capture date; claim effective dates come later."""

from collections.abc import Iterable
from datetime import date

from knowledge_now.models import SnapshotInfo


def parse_date(value: str) -> date:
    """Require an unambiguous calendar date such as 2026-05-31."""
    if not isinstance(value, str):
        raise ValueError("Dates must be strings in YYYY-MM-DD format.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD.")
    return parsed


def select_snapshot(
    snapshots: Iterable[SnapshotInfo], as_of: str | None = None
) -> SnapshotInfo | None:
    """Choose the newest capture on/before the requested date, or the newest capture."""
    cutoff = parse_date(as_of) if as_of is not None else None
    eligible = [
        snapshot
        for snapshot in snapshots
        if cutoff is None or parse_date(snapshot.taken_on) <= cutoff
    ]
    # The ID is a deterministic tie-breaker if two captures share a calendar date.
    return max(
        eligible,
        key=lambda snapshot: (parse_date(snapshot.taken_on), snapshot.snapshot_id),
        default=None,
    )
