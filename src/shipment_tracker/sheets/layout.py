"""Finding columns by their header text instead of by position.

If someone reorders columns or adds a new form question, we still find
Tracking and Status correctly, because we look them up by name.
"""

from __future__ import annotations

from dataclasses import dataclass

TRACKING_HEADER = "Tracking"
STATUS_HEADER = "Status"


class SheetLayoutError(ValueError):
    """The tab's header row isn't laid out the way we need. Nothing was written."""


@dataclass(frozen=True)
class StatusColumn:
    column: int  # 1-based
    needs_header: bool  # True if we must write "Status" into the header row first


def header_key(text: str) -> str:
    """Compare headers loosely: ' ZIP  Code ' matches 'zip code'."""
    return " ".join(text.split()).lower()


def find_column(header_row: list[str], name: str) -> int | None:
    """Return the 1-based column whose header matches `name`, or None."""
    wanted = header_key(name)
    for index, text in enumerate(header_row, start=1):
        if header_key(text) == wanted:
            return index
    return None


def tracking_column(header_row: list[str]) -> int:
    column = find_column(header_row, TRACKING_HEADER)
    if column is None:
        raise SheetLayoutError(f"No '{TRACKING_HEADER}' column in the header row: {header_row}")
    return column


def status_column(header_row: list[str]) -> StatusColumn:
    """Locate the Status column, or decide where to create it.

    * If a "Status" header exists anywhere, use it.
    * Otherwise use the column right after Tracking, but only if that
      column's header is empty. We refuse to take over a column that
      already belongs to something else.
    """
    existing = find_column(header_row, STATUS_HEADER)
    if existing is not None:
        return StatusColumn(existing, needs_header=False)

    proposed = tracking_column(header_row) + 1
    current_header = header_row[proposed - 1] if proposed <= len(header_row) else ""
    if current_header.strip():
        raise SheetLayoutError(
            f"No '{STATUS_HEADER}' column, and the column after Tracking is already "
            f"used for '{current_header}'. Add a '{STATUS_HEADER}' header where you want it."
        )
    return StatusColumn(proposed, needs_header=True)
