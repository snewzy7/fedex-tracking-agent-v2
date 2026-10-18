"""Writing statuses into the sheet safely.

Three safety rules, each covered by tests:

1. Only the Status column is ever written. `apply_status_updates` checks
   every single cell before writing and refuses the whole batch if any
   cell is outside the Status column (or is a header other than "Status").

2. Rows are matched by tracking number, not by row number. We re-read the
   tab right before writing, so if someone sorted or inserted rows while
   lookups were running, each status still lands next to its own number.

3. Only cells that actually change are written. Re-running is harmless,
   and a dry run is just "plan, but don't apply."
"""

from __future__ import annotations

from shipment_tracker.display import StatusCell
from shipment_tracker.sheets.base import CellUpdate, SheetClient
from shipment_tracker.sheets.layout import STATUS_HEADER, SheetLayoutError, status_column, tracking_column
from shipment_tracker.tracking_numbers import tracking_key


class UnsafeUpdateError(RuntimeError):
    """An update would have touched a cell the tool doesn't own. Nothing was written."""


def plan_status_updates(
    sheet: SheetClient, tab: str, statuses: dict[str, StatusCell]
) -> list[CellUpdate]:
    """Work out which Status cells need to change, without writing anything.

    `statuses` maps tracking_key(tracking cell) -> the StatusCell to show.
    Rows whose tracking number isn't in `statuses` are left alone.
    """
    rows = sheet.read_tab(tab)  # fresh read: rows may have moved since we looked them up
    if not rows:
        return []
    header = rows[0]
    tracking_col = tracking_column(header)
    target = status_column(header)

    updates = []
    for row_number, row in enumerate(rows[1:], start=2):
        key = tracking_key(_cell(row, tracking_col))
        new = statuses.get(key) if key else None
        if new is None:
            continue
        if _cell(row, target.column) == new.text:
            continue  # already up to date
        updates.append(CellUpdate(row=row_number, column=target.column, text=new.text, color=new.color))

    if updates and target.needs_header:
        updates.insert(0, CellUpdate(row=1, column=target.column, text=STATUS_HEADER, color=None))
    return updates


def check_layout(sheet: SheetClient, tab: str) -> None:
    """Raise SheetLayoutError now if we couldn't safely write this tab later.

    Called before any lookups, so a bad layout doesn't waste carrier calls.
    """
    rows = sheet.read_tab(tab)
    if rows:
        status_column(rows[0])  # also checks the Tracking column exists


def apply_status_updates(sheet: SheetClient, tab: str, updates: list[CellUpdate]) -> None:
    """Write planned updates after double-checking every cell is ours to write."""
    if not updates:
        return
    header = sheet.read_tab(tab)[0]
    allowed_column = _allowed_status_column(header, updates)

    for update in updates:
        if update.column != allowed_column:
            raise UnsafeUpdateError(
                f"Refusing to write row {update.row}, column {update.column}: "
                f"only the Status column ({allowed_column}) may be changed."
            )
        if update.row == 1 and update.text != STATUS_HEADER:
            raise UnsafeUpdateError(f"Refusing to change the header row to '{update.text}'.")
        if update.row < 1:
            raise UnsafeUpdateError(f"Invalid row number {update.row}.")

    sheet.write_cells(tab, updates)


def update_statuses(sheet: SheetClient, tab: str, statuses: dict[str, StatusCell]) -> list[CellUpdate]:
    """Plan and apply in one step. Returns what was written."""
    updates = plan_status_updates(sheet, tab, statuses)
    apply_status_updates(sheet, tab, updates)
    return updates


def _allowed_status_column(header: list[str], updates: list[CellUpdate]) -> int:
    target = status_column(header)
    if target.needs_header and not any(u.row == 1 and u.text == STATUS_HEADER for u in updates):
        raise SheetLayoutError("The Status header is missing and this batch doesn't create it.")
    return target.column


def _cell(row: list[str], column: int) -> str:
    return row[column - 1] if column <= len(row) else ""
