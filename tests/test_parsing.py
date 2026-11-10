"""Synthetic evidence checks: retain meaning and never lose the original citation."""

import hashlib

import pytest

from knowledge_now.ingestion import SnapshotStore, normalize_markdown
from knowledge_now.models import Page, Snapshot, StoredPage
from knowledge_now.parsing import build_evidence_units


def stored(markdown, snapshot_id="synthetic", url="https://example.test/rates"):
    return StoredPage(
        snapshot_id=snapshot_id,
        url=url,
        title="Example certificate rates",
        fetched_at="2026-01-01T00:00:00Z",
        markdown=markdown,
        normalized_markdown=normalize_markdown(markdown),
        content_hash=hashlib.sha256(markdown.encode()).hexdigest(),
    )


def test_table_retains_headers_every_row_and_nearby_notes():
    raw = (
        "# Savings\n\n## Certificates\n\nFixed specials\n\n"
        "| Term | Rate | APY | Minimum |\n"
        "| --- | --- | --- | --- |\n"
        "| 9 month jumbo | 3.15% | 3.20%1 | $90,000 |\n"
        "| 9 month standard | 3.05% | 3.10%2 | $900 |\n\n"
        "Rates effective January 1.\n\n1Jumbo account conditions apply.\n"
    )
    units = build_evidence_units(stored(raw))
    table = next(unit for unit in units if unit.kind == "table")
    assert table.headings == ("Savings", "Certificates")
    assert table.text.startswith("| Term | Rate | APY | Minimum |")
    assert "3.20%1" in table.text and "3.10%2" in table.text
    assert table.context_before == "Fixed specials"
    assert "Rates effective January 1." in table.context_after
    assert "1Jumbo account conditions apply." in table.context_after
    assert table.quote == "".join(
        raw.splitlines(keepends=True)[table.start_line - 1 : table.end_line]
    )
    assert table.url == "https://example.test/rates"
    assert "Example certificate rates" in table.search_text


def test_original_quotes_and_line_numbers_survive_crlf_normalization():
    raw = "# Example\r\n\r\nTerm | APY\r\n--- | ---\r\n9 months | 3.20%1\r\n"
    table = build_evidence_units(stored(raw))[0]
    assert table.kind == "table"
    assert (table.start_line, table.end_line) == (3, 5)
    assert table.quote == "".join(raw.splitlines(keepends=True)[2:5])
    assert "\r\n" in table.quote
    assert "\r" not in table.text


def test_tables_inside_code_fences_are_passages_and_do_not_create_heading_context():
    raw = "# Real\n\n```markdown\n# Not a heading\n| A | B |\n| --- | --- |\n```\n"
    units = build_evidence_units(stored(raw))
    assert len(units) == 1
    assert units[0].kind == "passage"
    assert units[0].headings == ("Real",)
    assert "# Not a heading" in units[0].text


def test_aligned_columns_escaped_pipes_and_table_without_blank_boundary():
    raw = (
        "A descriptive label\n"
        "Product | APY\n:--- | ---:\n"
        "Example \\| special | 3.20%\n"
        "## Another section\nUnrelated text.\n"
    )
    units = build_evidence_units(stored(raw))
    table = next(unit for unit in units if unit.kind == "table")
    assert table.context_before == "A descriptive label"
    assert "Example \\| special" in table.text
    assert table.context_after == ""
    assert "Unrelated" not in table.search_text


def test_heading_scope_changes_and_neighboring_tables_stay_separate():
    raw = (
        "# Accounts\n## Savings\nSavings note.\n\n"
        "A | B\n--- | ---\n1 | 2\n\n"
        "C | D\n--- | ---\n3 | 4\n\n"
        "## Loans\nLoan note.\n"
    )
    units = build_evidence_units(stored(raw))
    tables = [unit for unit in units if unit.kind == "table"]
    assert len(tables) == 2
    assert tables[0].headings == ("Accounts", "Savings")
    assert "C | D" not in tables[0].search_text
    assert "Loan note" not in tables[1].search_text
    assert units[-1].headings == ("Accounts", "Loans")


def test_adjacent_tables_and_pipe_in_heading_are_not_merged():
    raw = "A | B\n--- | ---\n1 | 2\nC | D\n--- | ---\n3 | 4\n## Rates | C#\nAnother passage.\n"
    units = build_evidence_units(stored(raw))
    tables = [unit for unit in units if unit.kind == "table"]
    assert len(tables) == 2
    assert "C | D" not in tables[0].text
    assert "## Rates" not in tables[1].text
    assert units[-1].headings == ("Rates | C#",)


def test_heading_without_a_body_remains_searchable():
    units = build_evidence_units(stored("# Example\n\n## Routing details\n"))
    assert len(units) == 1
    assert units[0].kind == "passage"
    assert units[0].quote == "## Routing details\n"
    assert "Example" in units[0].search_text
    assert "Routing details" in units[0].search_text


def test_large_table_is_not_cut_at_an_arbitrary_character_limit():
    rows = "".join(f"{index} months | 3.20%\n" for index in range(1, 101))
    raw = "Term | APY\n--- | ---\n" + rows
    units = build_evidence_units(stored(raw))
    assert len(units) == 1
    assert units[0].kind == "table"
    assert units[0].text == raw
    assert "100 months | 3.20%" in units[0].quote


def test_ids_are_repeatable_but_distinguish_source_versions_and_repeated_passages():
    raw = "Repeated.\n\nRepeated.\n"
    first = build_evidence_units(stored(raw))
    assert [unit.unit_id for unit in first] == [
        unit.unit_id for unit in build_evidence_units(stored(raw))
    ]
    assert first[0].unit_id != first[1].unit_id
    assert first[0].unit_id != build_evidence_units(stored(raw, snapshot_id="later"))[0].unit_id
    assert first[0].unit_id != build_evidence_units(stored(raw + "changed"))[0].unit_id
    assert (
        first[0].unit_id
        != build_evidence_units(stored(raw, url="https://example.test/other"))[0].unit_id
    )


def test_empty_input_and_unsafe_line_mapping():
    assert build_evidence_units(stored("\n\n")) == []
    page = stored("Original.\n")
    broken = StoredPage(
        page.snapshot_id,
        page.url,
        page.title,
        page.fetched_at,
        page.markdown,
        "Added line.\nOriginal.\n",
        page.content_hash,
    )
    with pytest.raises(ValueError, match="cannot cite safely"):
        build_evidence_units(broken)


def test_selected_capture_is_the_only_source_for_units():
    store = SnapshotStore()
    try:
        store.ingest(
            Snapshot("old", "2026-01-01", [Page("url", "Old", "Older evidence.", "2026-01-01")])
        )
        store.ingest(
            Snapshot("new", "2026-02-01", [Page("url", "New", "Future evidence.", "2026-02-01")])
        )
        selected = store.select("2026-01-31")
        units = [
            unit
            for page in store.pages(selected.snapshot_id)
            for unit in build_evidence_units(page)
        ]
        assert len(units) == 1
        assert units[0].snapshot_id == "old"
        assert units[0].text == "Older evidence."
    finally:
        store.close()
