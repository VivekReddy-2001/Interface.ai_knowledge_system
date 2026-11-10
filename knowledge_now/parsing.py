"""Turn stored Markdown into source-preserving evidence units; no claim resolution."""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

from knowledge_now.models import EvidenceUnit, StoredPage

HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
SEPARATOR_CELL = re.compile(r":?-{3,}:?")


@dataclass(frozen=True)
class _Block:
    """Internal zero-based line span; end is exclusive, like a Python slice."""

    kind: Literal["heading", "passage", "table"]
    start: int
    end: int
    headings: tuple[str, ...]


def _cells(line: str) -> list[str]:
    # A backslash-escaped pipe belongs inside a cell, not between two cells.
    cells = re.split(r"(?<!\\)\|", line.strip())
    if cells and not cells[0]:
        cells = cells[1:]
    if cells and not cells[-1]:
        cells = cells[:-1]
    return [cell.strip() for cell in cells]


def _starts_table(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header = _cells(lines[index])
    separator = _cells(lines[index + 1])
    return (
        len(header) >= 2
        and len(header) == len(separator)
        and all(SEPARATOR_CELL.fullmatch(cell) for cell in separator)
    )


def _blocks(lines: list[str]) -> list[_Block]:
    blocks = []
    headings: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        start = index
        heading = HEADING.match(lines[index])
        if heading:
            level, label = len(heading[1]), heading[2]
            headings = [(depth, text) for depth, text in headings if depth < level]
            headings.append((level, label))
            blocks.append(_Block("heading", index, index + 1, tuple(t for _, t in headings)))
            index += 1
            continue

        path = tuple(text for _, text in headings)
        fence = FENCE.match(lines[index])
        if fence:
            # Keep code examples whole and do not mistake their pipes for financial tables.
            marker = fence[1]
            index += 1
            while index < len(lines):
                closing = lines[index].strip()
                index += 1
                if len(closing) >= len(marker) and set(closing) == {marker[0]}:
                    break
            blocks.append(_Block("passage", start, index, path))
            continue

        if _starts_table(lines, index):
            index += 2  # Keep both the column headers and separator.
            while index < len(lines) and len(_cells(lines[index])) >= 2:
                if (
                    HEADING.match(lines[index])
                    or FENCE.match(lines[index])
                    or _starts_table(lines, index)
                ):
                    break
                index += 1
            blocks.append(_Block("table", start, index, path))
            continue

        index += 1
        while index < len(lines) and lines[index].strip():
            if (
                HEADING.match(lines[index])
                or FENCE.match(lines[index])
                or _starts_table(lines, index)
            ):
                break
            index += 1
        blocks.append(_Block("passage", start, index, path))
    return blocks


def _neighbor_context(blocks: list[_Block], index: int, direction: int, lines: list[str]) -> str:
    """Keep up to two adjacent passages; never borrow across a heading or another table."""
    nearby = []
    neighbor = index + direction
    while 0 <= neighbor < len(blocks) and len(nearby) < 2:
        block = blocks[neighbor]
        if block.kind != "passage":
            break
        nearby.append(block)
        neighbor += direction
    nearby.sort(key=lambda block: block.start)
    return "\n\n".join("".join(lines[block.start : block.end]).strip() for block in nearby)


def build_evidence_units(page: StoredPage) -> list[EvidenceUnit]:
    """Parse one page version only; callers choose the applicable snapshot first."""
    lines = page.normalized_markdown.splitlines(keepends=True)
    original = page.markdown.splitlines(keepends=True)
    if len(lines) != len(original):
        raise ValueError("Normalized and original line counts differ; cannot cite safely.")
    blocks = _blocks(lines)
    units = []
    for index, block in enumerate(blocks):
        if block.kind == "heading" and index + 1 < len(blocks):
            following = blocks[index + 1]
            if following.kind != "heading" or len(following.headings) > len(block.headings):
                continue  # A following body/subsection already carries this heading.
        identity = json.dumps(
            [page.snapshot_id, page.url, page.content_hash, block.start, block.end]
        )
        units.append(
            EvidenceUnit(
                unit_id=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                snapshot_id=page.snapshot_id,
                url=page.url,
                title=page.title,
                source_hash=page.content_hash,
                kind="passage" if block.kind == "heading" else block.kind,
                headings=block.headings,
                start_line=block.start + 1,
                end_line=block.end,
                text="".join(lines[block.start : block.end]),
                quote="".join(original[block.start : block.end]),
                context_before=_neighbor_context(blocks, index, -1, lines),
                context_after=_neighbor_context(blocks, index, 1, lines),
            )
        )
    return units
