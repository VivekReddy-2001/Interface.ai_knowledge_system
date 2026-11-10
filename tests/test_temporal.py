"""Date boundaries must never expose evidence from a later capture."""

import pytest

from knowledge_now.models import SnapshotInfo
from knowledge_now.temporal import parse_date, select_snapshot


@pytest.fixture
def captures():
    # Deliberately unsorted: selection must use dates, not input order or IDs.
    return [
        SnapshotInfo("a-new", "2026-03-01", 1),
        SnapshotInfo("z-old", "2026-01-01", 1),
        SnapshotInfo("middle", "2026-02-01", 1),
    ]


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (None, "a-new"),
        ("2026-02-01", "middle"),
        ("2026-02-28", "middle"),
        ("2026-01-01", "z-old"),
        ("2025-12-31", None),
        ("2027-01-01", "a-new"),
    ],
)
def test_capture_selection(captures, as_of, expected):
    selected = select_snapshot(captures, as_of)
    assert (selected.snapshot_id if selected else None) == expected


def test_no_captures_and_same_date_tie():
    assert select_snapshot([]) is None
    captures = [SnapshotInfo("a", "2026-01-01", 0), SnapshotInfo("b", "2026-01-01", 0)]
    assert select_snapshot(captures).snapshot_id == "b"
    assert select_snapshot(reversed(captures)).snapshot_id == "b"


@pytest.mark.parametrize("value", ["2026-02-30", "01/02/2026", "20260101", "", 20260101])
def test_invalid_dates_are_rejected(value):
    with pytest.raises(ValueError):
        parse_date(value)
